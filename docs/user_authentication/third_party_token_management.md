
```sequence {theme: 'simple'}
Title: Third party idp token management
Pbench-Dashboard->Web-Server:[1] GET login page
Web-Server->Pbench-Dashboard:[2] 200 login page
Pbench-Dashboard->Pbench-Dashboard:[3] Generate Authorization request
Pbench-Dashboard->Web-Server:[4] 302 Redirect to identity provider
Web-Server->Identity-Provider:[5] POST Authorization request
Identity-Provider->Web-Server:[6] 200 Authenticate User
Identity-Provider->Web-Server:[7] GET consent request
Web-Server->Identity-Provider:[8] POST consent request payload
Identity-Provider->Pbench-Dashboard:[9] 200 Authorization code
Pbench-Dashboard->Identity-Provider:[10] POST Token request
Identity-Provider->Pbench-Dashboard:[11] 200 Access/Refresh Token payload
Pbench-Dashboard->Pbench-Server:[12] Send Access_token to get Pbench token
Pbench-Server->Identity-Provider:[13] GET public Keys
Identity-Provider->Pbench-Server:[14] 200 Public key
Pbench-Server->Pbench-Server:[15] Validate the access token
Pbench-Server->Identity-Provider:[16] [Optional] POST userinfo endpoint
Pbench-Server->Pbench-Keycloak-server:[17] Exchange idp access token with Pbench token
Pbench-Keycloak-server->Pbench-Server:[18] 200 new Pbench access_token and refresh_token
Pbench-Server->Pbench-Dashboard:[19] 200 New Pbench token payload
Pbench-Dashboard->Pbench-Server:[20] Request access to preotected endpoint
Pbench-Server->Pbench-Server:[21] Validate Pbench token
Pbench-Server->Pbench-Server:[22] Role extraction from token
Pbench-Server->Pbench-Dashboard:[23] 200/401
```