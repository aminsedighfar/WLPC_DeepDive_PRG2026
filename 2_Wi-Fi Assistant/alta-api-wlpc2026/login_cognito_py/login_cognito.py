#!/usr/bin/env python3
from __future__ import annotations

import getpass
from typing import Any, Dict, Optional

import boto3
from pycognito.aws_srp import AWSSRP
from pycognito.exceptions import (
    SoftwareTokenMFAChallengeException,
    SMSMFAChallengeException,
)


class CognitoLoginError(Exception):
    pass


def _extract(auth: Dict[str, Any]) -> Dict[str, str]:
    """Extract tokens from Cognito AuthenticationResult."""
    out = {
        "id_token": auth.get("IdToken", ""),
        "access_token": auth.get("AccessToken", ""),
        "refresh_token": auth.get("RefreshToken", ""),
        "expires_in": str(auth.get("ExpiresIn", "")),
        "token_type": auth.get("TokenType", ""),
    }

    if not out["id_token"] and not out["access_token"]:
        raise CognitoLoginError("AuthenticationResult missing IdToken/AccessToken.")

    return out


def _respond_to_mfa_challenge(
    *,
    client,
    client_id: str,
    username: str,
    challenge: str,
    session: str,
    mfa_code: Optional[str],
    prompt_for_mfa: bool,
) -> Dict[str, str]:
    """Respond to SMS or TOTP MFA challenge."""
    if challenge not in ("SMS_MFA", "SOFTWARE_TOKEN_MFA"):
        raise CognitoLoginError(f"Unsupported MFA challenge: {challenge}")

    if not mfa_code and prompt_for_mfa:
        label = "SMS" if challenge == "SMS_MFA" else "TOTP"
        mfa_code = input(f"Enter {label} MFA code (6 digits): ").strip()

    if not mfa_code:
        raise CognitoLoginError("MFA required but no code provided.")

    responses = {"USERNAME": username}
    if challenge == "SMS_MFA":
        responses["SMS_MFA_CODE"] = mfa_code
    else:
        responses["SOFTWARE_TOKEN_MFA_CODE"] = mfa_code

    resp = client.respond_to_auth_challenge(
        ClientId=client_id,
        ChallengeName=challenge,
        Session=session,
        ChallengeResponses=responses,
    )

    auth = resp.get("AuthenticationResult")
    if not auth:
        raise CognitoLoginError("MFA challenge did not return tokens.")

    return _extract(auth)


def login_srp_with_optional_mfa(
    *,
    region: str,
    user_pool_id: str,
    client_id: str,
    username: str,
    password: str,
    mfa_code: Optional[str] = None,
    prompt_for_mfa: bool = True,
) -> Dict[str, str]:
    """
    Authenticate against AWS Cognito using SRP.
    Prompts for MFA code in the shell if required.
    """
    client = boto3.client("cognito-idp", region_name=region)

    srp = AWSSRP(
        username=username,
        password=password,
        pool_id=user_pool_id,
        client_id=client_id,
        client=client,
    )

    try:
        resp: Dict[str, Any] = srp.authenticate_user()

        # No MFA required
        auth = resp.get("AuthenticationResult")
        if auth:
            return _extract(auth)

        raise CognitoLoginError(f"Unexpected response: {resp}")

    except SoftwareTokenMFAChallengeException as e:
        tokens = e.args[1]
        return _respond_to_mfa_challenge(
            client=client,
            client_id=client_id,
            username=username,
            challenge="SOFTWARE_TOKEN_MFA",
            session=tokens["Session"],
            mfa_code=mfa_code,
            prompt_for_mfa=prompt_for_mfa,
        )

    except SMSMFAChallengeException as e:
        tokens = e.args[1]
        return _respond_to_mfa_challenge(
            client=client,
            client_id=client_id,
            username=username,
            challenge="SMS_MFA",
            session=tokens["Session"],
            mfa_code=mfa_code,
            prompt_for_mfa=prompt_for_mfa,
        )


if __name__ == "__main__":
    REGION = "us-east-1"
    USER_POOL_ID = "us-east-1_4QbA7N3Uy"
    CLIENT_ID = "24bk8l088t5bf31nuceoqb503q"

    username = input("Username/email: ").strip()
    password = getpass.getpass("Password: ")

    tokens = login_srp_with_optional_mfa(
        region=REGION,
        user_pool_id=USER_POOL_ID,
        client_id=CLIENT_ID,
        username=username,
        password=password,
        prompt_for_mfa=True,
    )

    print("ID token (JWT):", tokens["id_token"])