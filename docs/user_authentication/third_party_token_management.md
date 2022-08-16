
```sequence {theme: 'simple'}
title Third Party IDP Token Management

participant Pbench-Keycloak-server
participant Pbench-Server
participant Pbench-Dashboard
participant Identity-Provider

autonumber 1
Pbench-Dashboard->Pbench-Server: GET IAM scheme & link
Pbench-Server->Pbench-Dashboard: 200 authentication schema/link
Pbench-Dashboard->Identity-Provider: POST Authorization request
note over Identity-Provider: Authenticate User and request \nuser consent for Pbench
Identity-Provider->Pbench-Dashboard: 200 Authorization code response
Pbench-Dashboard->Identity-Provider: POST authorization code (Token request)
Identity-Provider->Pbench-Dashboard: 200 Access/Refresh Token payload response 
note over Identity-Provider,Pbench-Dashboard: {"access_token":<access_token>,\n"expires_in": 300,\n"refresh_expires_in": 1800,\n"refresh_token": <refresh_token>,\n"token_type": "Bearer",\n"id_token": <id_token>,...}
// Here the dashboard sends the newly acquired access token to the Pbench Server to start the token exchange process.
Pbench-Dashboard->Pbench-Server: POST /api/v1/pbench-token request (Bearer: External IDP Access Token)
Pbench-Server->Identity-Provider: GET public Key
Identity-Provider->Pbench-Server: 200 public key
Pbench-Server->Pbench-Server: Validate the access token
Pbench-Server->Identity-Provider: [Optional] POST userinfo endpoint
Identity-Provider->Pbench-Server:  200 userinfo response
note over Pbench-Server,Pbench-Dashboard: {"family_name": <surname>,\n"sub": <user_id>,\n"email_verified": <bool>,\n"email": <email>,\n"given_name": <given_name>,...}
// We exchange the Third-party IDP token with our internal Pbench token that should be used for accessing Pbench server resources.
// Pbench token might contain more metadata about user such as role/group associations.
Pbench-Server->Pbench-Keycloak-server: Exchange IDP access token \n(provided by the Pbench dashboard) \nwith Pbench token
Pbench-Keycloak-server->Pbench-Server: 200 new Pbench access_token and refresh_token
// Finally, the Pbench Server responds to the dashboard with the new pbench token in the response payload.
Pbench-Server->Pbench-Dashboard: 200 /api/v1/pbench-token reponse (new 'Pbench Access Token' in payload)
// Preceding is a pbench token retrival setup; 
// following is a requests which can be issued without repeating the preceding setup
Pbench-Dashboard->Pbench-Server: POST /api/v1/<restricted_endpoint> request (Bearer: Pbench Access Token)
note over Pbench-Server: Validation and Role extraction \nfrom the Pbench token
alt case 1
Pbench-Server->Pbench-Dashboard: 200 /api/v1/<restricted_endpoint> reponse
else case 2
Pbench-Server->Pbench-Dashboard: 401 /api/v1/<restricted_endpoint> reponse
end
```