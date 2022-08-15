
```sequence {theme: 'simple'}
Title: Third party idp token management
Pbench-Dashboard->Pbench-Server:[1] GET login page
Pbench-Server->Pbench-Dashboard:[2] 200 login page
Pbench-Dashboard->Pbench-Dashboard:[3] Generate Authorization request
Pbench-Dashboard->Identity-Provider:[4] POST Authorization request
Identity-Provider->Identity-Provider:[5] 200 Authenticate User
Identity-Provider->Identity-Provider:[6] GET consent
Identity-Provider->Pbench-Dashboard:[7] 200 Authorization code
Pbench-Dashboard->Identity-Provider:[8] POST Token request
Identity-Provider->Pbench-Dashboard:[9] 200 Access/Refresh Token payload
Pbench-Dashboard->Pbench-Server:[10] Send Access_token to get Pbench token
Pbench-Server->Identity-Provider:[11] GET public Keys
Identity-Provider->Pbench-Server:[12] 200 Public key
Pbench-Server->Pbench-Server:[13] Validate the access token
Pbench-Server->Identity-Provider:[14] [Optional] POST userinfo endpoint
Pbench-Server->Pbench-Keycloak-server:[15] Exchange idp access token with Pbench token
Pbench-Keycloak-server->Pbench-Server:[16] 200 new Pbench access_token and refresh_token
Pbench-Server->Pbench-Dashboard:[17] 200 New Pbench token payload
Pbench-Dashboard->Pbench-Server:[18] Request access to preotected endpoint
Pbench-Server->Pbench-Server:[19] Validate Pbench token
Pbench-Server->Pbench-Server:[20] Role extraction from token
Pbench-Server->Pbench-Dashboard:[21] 200/401
```