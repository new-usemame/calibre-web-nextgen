# Security

## Reporting

Report suspected vulnerabilities by opening a private security advisory at
<https://github.com/new-usemame/Calibre-Web-NextGen/security/advisories/new>.

Please do not file public issues for vulnerabilities.

## Verifying release artifacts

Every released image is signed with [cosign](https://github.com/sigstore/cosign)
keyless (Sigstore Fulcio + Rekor) and carries a SLSA build-provenance attestation.

Verify a pulled image:

```bash
cosign verify ghcr.io/new-usemame/calibre-web-nextgen:vX.Y.Z \
  --certificate-identity-regexp '^https://github.com/new-usemame/Calibre-Web-NextGen/.github/workflows/' \
  --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'
```

Inspect the build provenance:

```bash
gh attestation verify \
  oci://ghcr.io/new-usemame/calibre-web-nextgen:vX.Y.Z \
  --owner new-usemame
```

A passing verification means the image was built by this repo's release workflow,
on a GitHub-hosted runner, from the commit referenced in the attestation.

## Supported versions

The latest published GitHub Release receives security backports. Older releases
are best-effort.
