# Spec Kit provenance

Upstream: [github/spec-kit](https://github.com/github/spec-kit), tag v1.4.3,
commit `980b3d027f4bd7958c35f97f618d854b41320e3f`.

The generated official skills in `.agents/skills/`, templates, shell helpers,
bundled bug/assess extensions and base workflows retain upstream behavior.
Their license is preserved in [LICENSE.spec-kit](LICENSE.spec-kit).

Project-specific principles are in `memory/constitution.md`; project customization
is in `workflows/overlays/speckit/nearic-quality.yml` and the repository guides.
The `hireminds-feature`, `hireminds-bugfix` and `hireminds-assess` skills are project-authored
chat entry points that read these workflow definitions; they are not upstream skills.
The upstream license applies to the Spec Kit material, not as a license grant
for unrelated Nearic source or documentation.
