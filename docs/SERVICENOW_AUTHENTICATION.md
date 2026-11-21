# ServiceNow Authentication

Select exactly one authentication mode with SERVICENOW_AUTH_MODE. If absent,
the default is basic, preserving existing configurations. There is no automatic
fallback from OAuth to Basic. Assignment-group restrictions remain unchanged.

## Basic Authentication

```dotenv
SERVICENOW_AUTH_MODE=basic
SERVICENOW_HOST=https://<instance>.service-now.com
SERVICENOW_USERNAME=<existing-user>
SERVICENOW_PASSWORD="<existing-password>"
SERVICENOW_ASSIGNMENT_GROUPS=<approved-group-names>
```

## OAuth Service Account

```dotenv
SERVICENOW_AUTH_MODE=oauth_client_credentials
SERVICENOW_HOST=https://<instance>.service-now.com
SERVICENOW_CLIENT_ID=<application-client-id>
SERVICENOW_CLIENT_SECRET="<application-client-secret>"
SERVICENOW_OAUTH_CLIENT_AUTH_METHOD=client_secret_post
SERVICENOW_ASSIGNMENT_GROUPS=<approved-group-names>
```

Optional variables:
- SERVICENOW_TOKEN_URL: defaults to the instance URL plus /oauth_token.do.
  HTTPS on the same origin is required; redirects are not followed.
- SERVICENOW_OAUTH_SCOPE: omit unless administrators specify a scope value.
- SERVICENOW_USERNAME: optional identity for workflows that default caller or
  assignee to this value. It does not select or prove the OAuth execution user.
- SERVICENOW_OAUTH_CLIENT_AUTH_METHOD: client_secret_post (default) sends the
  application credentials in the form body; client_secret_basic sends them
  through HTTP Basic client authentication at the token endpoint only.

The platform must map the application to the intended service account and grant
the required roles, ACLs, and API access. No service account password is required
or sent in OAuth mode, even if an old password remains configured.
Tokens are kept in memory, reused, and reacquired before expiry. No refresh token
is required. API failures do not automatically replay writes or switch modes.
Never print, commit, or include secrets/tokens in artifacts. Retain TLS validation.

## Testing and Switching

Run mocked tests before live testing:
`python -m unittest discover -s tests -p 'test_servicenow_[ce]*.py'`

After an approved administrator handoff, populate the selected mode in .env and
start a fresh script process. Existing terminal variables can override .env;
use the repository's SERVICENOW_OVERRIDE_ENV option when appropriate.
First test a read-only lookup of an approved incident in an allowed assignment
group and verify the effective service account through platform audit evidence.
Live writes require separate authorization. Switch back by setting the mode to
basic with valid Basic credentials and restarting the script process.
