# Signing the Windows installer

Windows shows **"Unknown publisher"** and **"Windows protected your PC"** for any
installer that is not code-signed. No setting or code removes that: Windows only
trusts a digital signature from a certificate that a certificate authority issued
after checking who you are. Once the installer is signed, the prompts say
**Verified publisher: <the name on your certificate>**.

The build is ready for that: `desktop/scripts/sign.js` signs the app, installer
and uninstaller, and the release workflow can sign automatically. What it needs
from you is a certificate.

## 1. Get a code-signing certificate

| Option | Who can get it | Signs in GitHub Actions | Notes |
|---|---|---|---|
| **Azure Trusted Signing** (Microsoft) | Registered organisations in supported countries; individuals only in some countries. Check current eligibility when you apply. | Yes (built in here) | About US$10/month. Cheapest and fully automatic. |
| **Certum Code Signing in the Cloud** (SimplySign) | Individuals and companies worldwide | No (needs the SimplySign phone login) | Sign on your own Windows PC with `store` (below). |
| **SSL.com / Sectigo / DigiCert OV certificate** on a USB token | Individuals and companies worldwide | No (token must be plugged in) | Sign on your own Windows PC with `store`. |

The certificate shows the **verified legal name**: your company's name if a
company applies, or your own name if you apply as an individual. For it to say
"Xelora", register the business as Xelora and apply as that organisation.

**SmartScreen:** since 2024 even signed installers can still show "Windows
protected your PC" for a while. Every certificate type now starts with no
reputation, and the warning goes away once enough people have installed that
signed file. Signing every release with the same certificate builds that
reputation. Unsigned builds never get it.

## 2. Sign

The method is chosen with `XELORA_SIGN_PROVIDER`. With it unset, builds are
left unsigned (fine for testing).

### Azure Trusted Signing (automatic, in GitHub Actions)

1. In Azure, create a Trusted Signing account, finish identity validation, and
   create a certificate profile.
2. Create an app registration and give it the **Trusted Signing Certificate
   Profile Signer** role on that account.
3. In GitHub → repository **Settings → Secrets and variables → Actions**:
   - Secrets: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
   - Variables: `XELORA_SIGN_PROVIDER=azure`, `AZURE_SIGN_ENDPOINT` (e.g.
     `https://eus.codesigning.azure.net`), `AZURE_SIGN_ACCOUNT`,
     `AZURE_SIGN_PROFILE`, and `XELORA_REQUIRE_SIGNING=true`
4. Push a `v*.*.*` tag. The workflow installs the signing client and signs
   during the build. With `XELORA_REQUIRE_SIGNING=true`, a release fails
   instead of going out unsigned.

### Certificate on your PC: USB token or Certum SimplySign

On the Windows PC that builds the installer (Windows SDK installed for
`signtool`), log in to the token or SimplySign so the certificate shows up in
the Windows certificate store. Then, in PowerShell:

```powershell
# Thumbprint of your code-signing certificate:
Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Format-List Subject, Thumbprint

cd desktop
$env:XELORA_SIGN_PROVIDER = "store"
$env:XELORA_CERT_SHA1 = "<thumbprint>"
npm run dist
```

Upload `release/Xelora-Setup-<version>.exe` and `release/latest.yml` to the
GitHub Release for that version.

### .pfx file

Only for certificates still delivered as a file: `XELORA_SIGN_PROVIDER=pfx`,
`XELORA_PFX_PATH`, `XELORA_PFX_PASSWORD`.

## 3. Check it

Right-click the installer → **Properties → Digital Signatures**. Your certificate
should be listed, with a timestamp. Or run `signtool verify /pa /v Xelora-Setup-<version>.exe`.

Once releases are signed, add `"publisherName": ["<exact name on the certificate>"]`
under `build.win` in `desktop/package.json`. Auto-updates then refuse an update
that is not signed by you. Don't add it while builds are unsigned, because then
every update would be rejected.

## What the build already does without a certificate

- The Xelora icon on the app, installer, uninstaller and shortcuts
- Product name, company name and description "Xelora" in the file properties
- Installer named `Xelora-Setup-<version>.exe`

The "Unknown publisher" line stays until a certificate is added.
