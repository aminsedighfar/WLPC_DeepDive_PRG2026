#!/usr/bin/env node
import promptSync from "prompt-sync";
import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
} from "amazon-cognito-identity-js";

const prompt = promptSync({ sigint: true });

/* ===== Static Cognito config (Alta) ===== */
const UserPoolId = "us-east-1_4QbA7N3Uy";
const ClientId = "24bk8l088t5bf31nuceoqb503q";

/* ===== Cognito helpers ===== */
function getUserPool() {
  return new CognitoUserPool({ UserPoolId, ClientId });
}

function getCognitoUser(userPool, username) {
  return new CognitoUser({ Pool: userPool, Username: username });
}

function getAuthenticationDetails(username, password) {
  return new AuthenticationDetails({ Username: username, Password: password });
}

/* ===== Auth flow ===== */
async function getIdTokenJwt() {
  const username = prompt("Username/email: ");
  const password = prompt.hide("Password: ");

  const userPool = getUserPool();
  const cognitoUser = getCognitoUser(userPool, username);
  const authenticationDetails = getAuthenticationDetails(username, password);

  return new Promise((resolve) => {
    cognitoUser.authenticateUser(authenticationDetails, {
      onSuccess: (result) => {
        resolve(result.getIdToken().getJwtToken());
      },

      onFailure: (err) => {
        console.error("Authentication failed:", err);
        resolve(null);
      },

      /* ===== SMS MFA ===== */
      mfaRequired: () => {
        const code = prompt("Enter SMS MFA code (6 digits): ");
        cognitoUser.sendMFACode(
          code,
          {
            onSuccess: (result) => resolve(result.getIdToken().getJwtToken()),
            onFailure: (err) => {
              console.error("SMS MFA failed:", err);
              resolve(null);
            },
          },
          "SMS_MFA"
        );
      },

      /* ===== TOTP / Authenticator app ===== */
      totpRequired: () => {
        const code = prompt("Enter TOTP code (6 digits): ");
        cognitoUser.sendMFACode(
          code,
          {
            onSuccess: (result) => resolve(result.getIdToken().getJwtToken()),
            onFailure: (err) => {
              console.error("TOTP MFA failed:", err);
              resolve(null);
            },
          },
          "SOFTWARE_TOKEN_MFA"
        );
      },

      /* ===== Forced password change (edge case) ===== */
      newPasswordRequired: (userAttributes) => {
        // Cognito requires removing these attributes if present
        delete userAttributes.email_verified;
        delete userAttributes.phone_number_verified;

        const newPassword = prompt.hide(
          "New password required. Enter new password: "
        );

        cognitoUser.completeNewPasswordChallenge(
          newPassword,
          userAttributes,
          {
            onSuccess: (result) => resolve(result.getIdToken().getJwtToken()),
            onFailure: (err) => {
              console.error("New password challenge failed:", err);
              resolve(null);
            },
          }
        );
      },
    });
  });
}

/* ===== Entrypoint ===== */
(async () => {
  const jwt = await getIdTokenJwt();
  if (!jwt) {
    process.exitCode = 1;
    return;
  }
  console.log(jwt); // Full ID token JWT (for Postman/curl)
})();