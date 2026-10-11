# Cognito User Pool Login (Node.js CLI) — SRP with optional MFA (TOTP/SMS)

This is a **Node.js CLI utility** that authenticates a user against **AWS Cognito User Pools**
using `amazon-cognito-identity-js` and prints a valid **ID token (JWT)**.

It is intended for **internal use** (debugging, Postman testing, support workflows).

---

## Features

- Prompts for **username/email**
- Prompts for **password** (hidden input)
- Supports MFA:
  - TOTP / authenticator app (`SOFTWARE_TOKEN_MFA`)
  - SMS MFA (`SMS_MFA`)
- Handles forced password change (`newPasswordRequired`)
- Prints the **full JWT** to stdout

> This script performs **Cognito authentication only**.  
> It does **not** call the Alta API directly.

---

## Requirements

- Node.js (recommended: Node 18+)
- npm

---

## Install

From an empty directory:

```bash
mkdir cognito-node
cd cognito-node
npm init -y
npm install amazon-cognito-identity-js prompt-sync
```

---

## Files

Save the script as:

```
login_cognito.mjs
```

(The `.mjs` extension ensures ES module support.)

---

## Configuration (Alta)

For Alta usage, these Cognito values are **static** and should not be modified unless
the Cognito configuration changes:

```js
const UserPoolId = "us-east-1_4QbA7N3Uy";
const ClientId   = "24bk8l088t5bf31nuceoqb503q";
```

> The script can be reused with other Cognito User Pools by changing these values,
> but that is out of scope for Alta API usage.

---

## Usage

Run:

```bash
node login_cognito.mjs
```

You will be prompted for:

- Username/email
- Password (hidden)
- MFA code (only if required)

On success, the script prints the **full ID token (JWT)** to stdout.

---

## Example (redacted)

```text
$ node login_cognito.mjs
Username/email: user@example.com
Password:
Enter TOTP code (6 digits): ******
eyJhbGciOi...<redacted>
```

---

## MFA Behavior

If MFA is enabled for the account, Cognito may require:

- `SOFTWARE_TOKEN_MFA` — authenticator app (TOTP)
- `SMS_MFA` — text message

The script will automatically prompt for the appropriate 6-digit code.

---

## Security Notes

- **Do not commit real JWTs, passwords, or MFA codes**
- Avoid screenshots that include real tokens or user email addresses
- Treat printed tokens as **bearer credentials**

---

## Troubleshooting

### Authentication fails
Verify:
- Correct username/password
- User exists in the expected Cognito User Pool
- User Pool ID and Client ID are correct

### Node runtime issues
`amazon-cognito-identity-js` was originally browser-oriented.  
Most modern Node versions work without issue, but if you encounter crypto/polyfill
errors, capture:

- `node -v`
- Full error output

…and adjust accordingly.

---

## Notes

This script is intended as a **CLI helper** for obtaining Cognito-issued tokens.
How the token is used (Postman, curl, API calls) is outside the scope of this repo.