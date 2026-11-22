# Security policy

## Supported releases

Security fixes are made against the latest release. Older releases may not receive fixes; upgrade to the latest image or release before reporting an issue.

## Report a vulnerability privately

Use GitHub's **Report a vulnerability** action on the repository's Security tab. Do not report vulnerabilities in public issues, discussions, or pull requests. If private reporting is unavailable, contact the maintainers through [GitHub](https://github.com/paladini) without publishing exploit details.

Please include the affected version or image tag, deployment profile, host OS and architecture, the operation involved, impact, and safe reproduction details. Never attach private source documents, credentials, or unrelated personal data.

## Security model

This is a self-hosted file-processing application. The web service is unauthenticated by default; operators must restrict access to trusted users and networks. Uploaded files, job metadata, and results are stored on the host in the configured data directory until retention cleanup. Workers process files locally and run without network access. Public URL conversion is an explicit exception: the web process fetches bounded public HTTP(S) pages and static assets, while blocking non-public destinations. See the README for operational limits. No hosted processing or analytics is used.

These boundaries do not replace access control at the operator's reverse proxy or network edge.
