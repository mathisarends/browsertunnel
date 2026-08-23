import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pyrpckit.codegen.ir import (
    AliasDecl,
    ClientIr,
    EnumDecl,
    EnumLiteralType,
    ListType,
    LiteralType,
    MapType,
    ModelDecl,
    NamedType,
    OperationDecl,
    Primitive,
    PrimitiveType,
    TypeExpr,
    UnionType,
    build_ir,
    named_types,
)

GENERATED_HEADER = "// Generated from {source}. Do not edit manually.\n"


@dataclass(frozen=True, slots=True)
class TypeScriptClientOptions:
    client_name: str = "RpcClient"
    source: str = "the OpenRPC document"


def render_typescript_client(
    document: dict[str, Any], options: TypeScriptClientOptions
) -> dict[str, str]:
    ir = build_ir(_normalize_inline_enums(document))
    renderer = _Renderer(ir, options)
    return {
        "models.ts": renderer.models(),
        "client.ts": renderer.client(),
        "index.ts": renderer.index(),
    }


def write_typescript_client(
    document: dict[str, Any],
    output_dir: Path,
    options: TypeScriptClientOptions,
    *,
    check: bool = False,
) -> tuple[Path, ...]:
    changed: list[Path] = []
    for relative_path, content in render_typescript_client(document, options).items():
        path = output_dir / relative_path
        if path.exists() and path.read_text(encoding="utf-8") == content:
            continue
        changed.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    return tuple(changed)


class _Renderer:
    def __init__(self, ir: ClientIr, options: TypeScriptClientOptions) -> None:
        self.ir = ir
        self.options = options

    def models(self) -> str:
        blocks = [self._enum(self.ir.method_enum)]
        blocks.extend(
            self._declaration(declaration) for declaration in self.ir.declarations
        )
        return self._module("\n\n".join(blocks))

    def client(self) -> str:
        model_names = self._client_model_names()
        imports = ['import { RpcMethod } from "./models";']
        if model_names:
            joined = "\n".join(f"  {name}," for name in sorted(model_names))
            imports.append(f'import type {{\n{joined}\n}} from "./models";')
        imports.append('import type { RpcTransport } from "../transport";')

        namespaces = "\n\n".join(
            self._namespace(namespace.name, namespace.operations)
            for namespace in self.ir.namespaces
        )
        root = self._root_client()
        body = "\n\n".join(
            part for part in ("\n".join(imports), namespaces, root) if part
        )
        return self._module(body)

    def index(self) -> str:
        return self._module(
            'export { RpcMethod } from "./models";\n'
            'export type * from "./models";\n'
            f'export {{ {self.options.client_name} }} from "./client";'
        )

    def _module(self, body: str) -> str:
        return f"{GENERATED_HEADER.format(source=self.options.source)}\n{body}\n"

    def _declaration(self, declaration: object) -> str:
        if isinstance(declaration, EnumDecl):
            return self._enum(declaration)
        if isinstance(declaration, ModelDecl):
            return self._model(declaration)
        if isinstance(declaration, AliasDecl):
            return f"export type {declaration.name} = {self._type(declaration.target)};"
        raise TypeError(f"Unsupported declaration: {type(declaration).__name__}")

    def _enum(self, declaration: EnumDecl) -> str:
        members = "\n".join(
            f"  {member.name}: {json.dumps(member.value)},"
            for member in declaration.members
        )
        return (
            f"export const {declaration.name} = {{\n{members}\n}} as const;\n\n"
            f"export type {declaration.name} = "
            f"(typeof {declaration.name})[keyof typeof {declaration.name}];"
        )

    def _model(self, declaration: ModelDecl) -> str:
        if not declaration.fields:
            return f"export type {declaration.name} = Record<string, never>;"
        rendered_fields: list[str] = []
        for field in declaration.fields:
            discriminator = _is_discriminator(field.name, field.type)
            optional = "?" if not field.required and not discriminator else ""
            rendered_fields.append(
                f"  {self._property(field.name)}{optional}: {self._type(field.type)};"
            )
        fields = "\n".join(rendered_fields)
        return f"export type {declaration.name} = {{\n{fields}\n}};"

    def _type(self, expression: TypeExpr) -> str:
        if isinstance(expression, PrimitiveType):
            return _PRIMITIVES[expression.primitive]
        if isinstance(expression, NamedType):
            return expression.name
        if isinstance(expression, LiteralType):
            return json.dumps(expression.value)
        if isinstance(expression, EnumLiteralType):
            return f"typeof {expression.enum}.{expression.member}"
        if isinstance(expression, ListType):
            item = self._type(expression.item)
            if isinstance(expression.item, UnionType):
                item = f"({item})"
            return f"{item}[]"
        if isinstance(expression, MapType):
            return f"Record<string, {self._type(expression.value)}>"
        if isinstance(expression, UnionType):
            return " | ".join(
                dict.fromkeys(self._type(member) for member in expression.members)
            )
        raise TypeError(f"Unsupported type: {type(expression).__name__}")

    def _namespace(self, namespace: str, operations: tuple[OperationDecl, ...]) -> str:
        class_name = self._namespace_class(namespace)
        methods = "\n\n".join(self._operation(operation) for operation in operations)
        return (
            f"class {class_name} {{\n"
            "  constructor(private readonly transport: RpcTransport) {}\n\n"
            f"{methods}\n"
            "}"
        )

    def _root_client(self) -> str:
        tree: dict[str, Any] = {}
        for namespace in self.ir.namespaces:
            cursor = tree
            for segment in namespace.name.split("."):
                cursor = cursor.setdefault(segment, {})
            cursor["$class"] = self._namespace_class(namespace.name)

        lines = [f"export class {self.options.client_name} {{"]
        for name in tree:
            lines.append(f"  readonly {self._property(name)};")
        lines.append("")
        lines.append("  constructor(private readonly transport: RpcTransport) {")
        for name, node in tree.items():
            lines.extend(self._tree_assignment(name, node))
        lines.append("  }")
        for operation in self.ir.root_operations:
            lines.extend(["", self._operation(operation)])
        if self.ir.notifications:
            notification = self.ir.notifications[0]
            message_type = self._type(notification.message)
            lines.extend(
                [
                    "",
                    f"  async *notifications(): AsyncIterable<{message_type}> {{",
                    "    for await (const message of this.transport.notifications()) {",
                    f"      yield message as {message_type};",
                    "    }",
                    "  }",
                ]
            )
        lines.extend(
            [
                "",
                "  close(): Promise<void> {",
                "    return this.transport.close();",
                "  }",
                "}",
            ]
        )
        return "\n".join(lines)

    def _tree_assignment(self, name: str, node: dict[str, Any]) -> list[str]:
        rendered = self._tree_object(node, indent=6)
        return [f"    this.{self._property(name)} = {rendered};"]

    def _tree_object(self, node: dict[str, Any], *, indent: int) -> str:
        class_name = node.get("$class")
        children = [(name, child) for name, child in node.items() if name != "$class"]
        if class_name and not children:
            return f"new {class_name}(this.transport)"
        if class_name:
            lines = [f"Object.assign(new {class_name}(this.transport), {{"]
        else:
            lines = ["{"]
        for name, child in children:
            value = self._tree_object(child, indent=indent + 2)
            lines.append(" " * indent + f"{self._property(name)}: {value},")
        suffix = "} as const)" if class_name else "} as const"
        lines.append(" " * (indent - 2) + suffix)
        return "\n".join(lines)

    def _operation(self, operation: OperationDecl) -> str:
        params = ""
        request_params = "{}"
        if operation.params:
            required = any(parameter.required for parameter in operation.params)
            default = "" if required else " = {}"
            params = f"params: {operation.params_model}{default}"
            request_params = "params"
        wire_result = self._type(operation.result)
        result = "void" if _is_null(operation.result) else wire_result
        lines: list[str] = []
        if operation.summary:
            lines.append(f"  /** {operation.summary.strip()} */")
        async_prefix = "async " if _is_null(operation.result) else ""
        method_name = self._identifier(operation.name)
        lines.append(f"  {async_prefix}{method_name}({params}): Promise<{result}> {{")
        if _is_null(operation.result):
            lines.append("    await this.transport.request<null>(")
        else:
            lines.append(f"    return this.transport.request<{wire_result}>(")
        lines.extend(
            [
                f"      RpcMethod.{operation.method_member},",
                f"      {request_params},",
                "    );",
                "  }",
            ]
        )
        return "\n".join(lines)

    def _client_model_names(self) -> set[str]:
        names = {
            operation.params_model
            for operation in self.ir.operations
            if operation.params
        }
        for operation in self.ir.operations:
            names.update(named_types(operation.result))
        for notification in self.ir.notifications:
            names.update(named_types(notification.message))
        return names

    @staticmethod
    def _namespace_class(namespace: str) -> str:
        return f"{_pascal_case(namespace)}Client"

    @staticmethod
    def _identifier(value: str) -> str:
        identifier = re.sub(r"[^A-Za-z0-9_$]", "_", value)
        if not identifier or identifier[0].isdigit() or identifier in _RESERVED_WORDS:
            return f"{identifier}_"
        return identifier

    @classmethod
    def _property(cls, value: str) -> str:
        identifier = cls._identifier(value)
        return identifier if identifier.rstrip("_") == value else json.dumps(value)


def _pascal_case(value: str) -> str:
    return "".join(
        part[:1].upper() + part[1:] for part in re.split(r"[._\- ]", value) if part
    )


def _is_discriminator(name: str, expression: TypeExpr) -> bool:
    return name == "type" and isinstance(expression, (LiteralType, EnumLiteralType))


def _is_null(expression: TypeExpr) -> bool:
    return (
        isinstance(expression, PrimitiveType) and expression.primitive is Primitive.NULL
    )


def _normalize_inline_enums(document: dict[str, Any]) -> dict[str, Any]:
    """Express inline JSON Schema enums in the subset understood by ClientIr."""
    normalized = deepcopy(document)
    component_schemas = normalized.get("components", {}).get("schemas", {})
    for schema in component_schemas.values():
        _normalize_schema_children(schema)
    for method in normalized.get("methods", []):
        for parameter in method.get("params", []):
            _normalize_schema(parameter.get("schema"))
        _normalize_schema(method.get("result", {}).get("schema"))
    return normalized


def _normalize_schema_children(value: object) -> None:
    if isinstance(value, dict):
        for child in value.values():
            _normalize_schema(child)
    elif isinstance(value, list):
        for child in value:
            _normalize_schema(child)


def _normalize_schema(value: object) -> None:
    if isinstance(value, dict):
        enum = value.get("enum")
        if isinstance(enum, list):
            value.pop("enum")
            value["anyOf"] = [{"const": item} for item in enum]
        _normalize_schema_children(value)
    elif isinstance(value, list):
        for child in value:
            _normalize_schema(child)


_PRIMITIVES = {
    Primitive.STRING: "string",
    Primitive.INTEGER: "number",
    Primitive.NUMBER: "number",
    Primitive.BOOLEAN: "boolean",
    Primitive.NULL: "null",
    Primitive.UUID: "string",
    Primitive.DATETIME: "string",
    Primitive.ANY: "unknown",
}

_RESERVED_WORDS = frozenset(
    {
        "break",
        "case",
        "class",
        "const",
        "constructor",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "import",
        "in",
        "instanceof",
        "new",
        "null",
        "return",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "yield",
    }
)
