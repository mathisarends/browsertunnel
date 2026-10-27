# Lit Canon source snapshot

`lit-canon-composition` was not available on npm when this integration was made.
The committed npm archive is built from the unmodified `packages/composition`
source and manifest at upstream commit
[`4fe0827b03bacc3f04008b8300b3e6942593c323`](https://github.com/mathisarends/lit-canon/tree/4fe0827b03bacc3f04008b8300b3e6942593c323/packages/composition).
It includes the upstream MIT license. `lit-canon.json` records the source,
compiler version and archive SHA-256; `package-lock.json` records npm's integrity
hash. `package.json` installs the archive through an exact local file reference.

To rebuild, check out that commit, install its build peers (`lit@3.3.3`,
`@lit/context@1.1.6`, `@lit-labs/router@0.1.4`, `@tanstack/lit-query@0.2.25`)
and `typescript@6.0.3` in an isolated copy of `packages/composition`, then run
`tsc -p tsconfig.build.json`. Restore the original package manifest if the
install command changed it, and run `npm pack --ignore-scripts`. The consumer
only imports the composition entry point; TanStack Query is an optional peer.

For an upgrade, review the upstream migration/agent guides, rebuild from one
explicit commit, update the archive and provenance together, run `npm install
--ignore-scripts` to update the lockfile, then run the documented application
checks. Once a suitable npm release exists, it can replace the archive with an
exact registry version after those checks pass.
