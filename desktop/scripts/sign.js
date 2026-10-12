/**
 * Code-signs every Windows executable electron-builder produces (the app,
 * the installer, the uninstaller), so Windows shows "Verified publisher:
 * <your certificate's name>" instead of "Unknown publisher".
 *
 * Signing needs a code-signing certificate issued to you or your company;
 * see docs/CODE_SIGNING.md. Pick the method with XELORA_SIGN_PROVIDER:
 *
 *   azure  Azure Trusted Signing (cloud; works in GitHub Actions)
 *            AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET,
 *            AZURE_SIGN_ENDPOINT, AZURE_SIGN_ACCOUNT, AZURE_SIGN_PROFILE,
 *            AZURE_SIGN_DLIB (path to Azure.CodeSigning.Dlib.dll)
 *   store  a certificate in the Windows certificate store: a USB token, or a
 *          cloud card such as Certum SimplySign (sign on your own PC)
 *            XELORA_CERT_SHA1 (the certificate's thumbprint)
 *   pfx    a .pfx file (only for certificates issued as files)
 *            XELORA_PFX_PATH, XELORA_PFX_PASSWORD
 *
 * Unset: the build is left unsigned (fine for testing). Set
 * XELORA_REQUIRE_SIGNING=true on release builds to fail instead.
 */
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const TIMESTAMP_URL = process.env.XELORA_TIMESTAMP_URL || 'http://timestamp.digicert.com';

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Code signing: ${name} is not set (XELORA_SIGN_PROVIDER=${process.env.XELORA_SIGN_PROVIDER}).`);
  return value;
}

function signtool() {
  if (process.env.SIGNTOOL_PATH) return process.env.SIGNTOOL_PATH;
  const kits = 'C:\\Program Files (x86)\\Windows Kits\\10\\bin';
  const versions = fs.existsSync(kits)
    ? fs.readdirSync(kits).filter((name) => /^10\./.test(name)).sort().reverse()
    : [];
  for (const version of versions) {
    const candidate = path.join(kits, version, 'x64', 'signtool.exe');
    if (fs.existsSync(candidate)) return candidate;
  }
  throw new Error('Code signing: signtool.exe not found. Install the Windows SDK or set SIGNTOOL_PATH.');
}

function run(args) {
  execFileSync(signtool(), args, { stdio: 'inherit' });
}

function signWithAzure(file) {
  const metadata = path.join(os.tmpdir(), 'xelora-trusted-signing.json');
  fs.writeFileSync(metadata, JSON.stringify({
    Endpoint: required('AZURE_SIGN_ENDPOINT'),
    CodeSigningAccountName: required('AZURE_SIGN_ACCOUNT'),
    CertificateProfileName: required('AZURE_SIGN_PROFILE'),
  }));
  required('AZURE_TENANT_ID');
  required('AZURE_CLIENT_ID');
  required('AZURE_CLIENT_SECRET');
  run(['sign', '/v', '/fd', 'SHA256', '/tr', 'http://timestamp.acs.microsoft.com', '/td', 'SHA256',
    '/dlib', required('AZURE_SIGN_DLIB'), '/dmdf', metadata, file]);
}

function signWithStore(file) {
  run(['sign', '/v', '/sha1', required('XELORA_CERT_SHA1'), '/fd', 'SHA256', '/tr', TIMESTAMP_URL, '/td', 'SHA256', file]);
}

function signWithPfx(file) {
  run(['sign', '/v', '/f', required('XELORA_PFX_PATH'), '/p', required('XELORA_PFX_PASSWORD'),
    '/fd', 'SHA256', '/tr', TIMESTAMP_URL, '/td', 'SHA256', file]);
}

const PROVIDERS = { azure: signWithAzure, store: signWithStore, pfx: signWithPfx };

exports.default = async function sign(configuration) {
  const file = configuration.path;
  const provider = (process.env.XELORA_SIGN_PROVIDER || '').trim().toLowerCase();
  if (!provider) {
    if (process.env.XELORA_REQUIRE_SIGNING === 'true') {
      throw new Error('Code signing is required for this build but XELORA_SIGN_PROVIDER is not set.');
    }
    console.log(`  • not signing ${path.basename(file)} (XELORA_SIGN_PROVIDER is not set)`);
    return;
  }
  const signer = PROVIDERS[provider];
  if (!signer) throw new Error(`Code signing: unknown XELORA_SIGN_PROVIDER "${provider}" (use azure, store or pfx).`);
  console.log(`  • signing ${path.basename(file)} with ${provider}`);
  signer(file);
  run(['verify', '/pa', file]);  // fail the build rather than ship a broken signature
};
