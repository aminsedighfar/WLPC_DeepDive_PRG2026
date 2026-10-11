# Cognito SRP Login (Python) — with optional MFA (TOTP/SMS)

This script authenticates a user against **AWS Cognito User Pools** using **SRP**
and returns JWTs. If the account requires MFA, it prompts for a 6-digit code
(TOTP/authenticator app or SMS) in the terminal and completes authentication.

For **Alta API usage**, the Cognito configuration values in this script are
**static** and do not change.

---

## Requirements

- Python 3.x
- `boto3`
- `pycognito`

Install dependencies:

```bash
pip install boto3 pycognito
```

(Recommended) Use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install boto3 pycognito
```

---

## Configuration (Alta)

For Alta API access, these values are **fixed** and should not be modified:

```py
REGION = "us-east-1"
USER_POOL_ID = "us-east-1_4QbA7N3Uy"
CLIENT_ID = "24bk8l088t5bf31nuceoqb503q"
```

They correspond to Alta’s Cognito User Pool and App Client.

Note: The script can be reused with other Cognito User Pools by changing
these values, but that is **out of scope** for Alta API usage.

---

## Usage

Run:

```bash
python login_cognito.py
```

You will be prompted for:

- Username / email
- Password
- MFA code (only if required)

---

## Example (redacted)

```text
$ python login_cognito.py
Username/email: user@example.com
Password:
Enter TOTP MFA code (6 digits): ******
ID token (JWT): eyJhbGciOi...<redacted>
```

---

## MFA behavior

If MFA is enabled on the user account, Cognito may require:

- `SOFTWARE_TOKEN_MFA` (TOTP / authenticator app)
- `SMS_MFA` (text message)

When challenged, the script prompts in the shell for a 6-digit code.

---

## Security notes

- **Do not commit real tokens, passwords, or MFA codes**
- Avoid screenshots that include real JWTs or email addresses
- If sharing output, fully redact tokens or use placeholder values

---

## Troubleshooting

### MFA challenge exception
Expected for accounts with MFA enabled. The script will prompt for the code
and continue automatically.

### Authentication failures
Verify the username/password and that the Cognito configuration values are
correct for Alta.

---

## Notes

This script performs **Cognito authentication only**. It does not call the
Alta API directly; the resulting JWT is intended to be supplied to Alta API
requests as documented elsewhere.