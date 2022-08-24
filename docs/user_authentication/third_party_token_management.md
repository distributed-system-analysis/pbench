
```sequence {theme: 'simple'}
title Third-party Token Management

participant Pbench-Server
participant Pbench-Dashboard
participant Identity-Broker
participant Identity-Provider

autonumber 1
Pbench-Dashboard->Pbench-Server: GET Pbench client ID

Pbench-Server->Pbench-Dashboard: 200 Response 

note over Pbench-Server,Pbench-Dashboard:{Identity_Broker_auth_URI: <auth_URI>\nclient_id: <pbench_client_id>\nclient_secret: <pbench_client_secret> # optional\n}

note over Pbench-Dashboard:User clicks login

Pbench-Dashboard->Identity-Broker:LOAD identity broker auth URI\n(Authentication Request)

note right of Pbench-Dashboard:GET request:\n<identity_broker_auth_URI>\n?client_id=<pbench_client_id>\n&response_type=code\n&redirect_uri=<dashboard_URI>\n&scope=openid

note over Identity-Broker:User selects an identity provider from the list

Identity-Broker->Identity-Provider:LOAD identity provider auth page

note right of Identity-Broker:GET request:\n<identity_provider_auth_URI>\n?client_id=<client_id as registered on identity provider>\n&response_type=code\n&redirect_uri=<identity_broker_URI>\n&scope=openid

note over Identity-Provider:User challenge credentials and consent

Identity-Provider->Identity-Broker:302 Authentication Response\n(Redirect back to identity broker)

note left of Identity-Provider:Redirect Location:\n<Identity_broker_URI>\n?code=<auth_code>\n&state=<session_state_id>

note over Identity-Broker:Identity federation\na. Checks the validity of response from the Identity provider\nb. Imports and creates user identity from the token\nc. Links the user identity with the Identity provider

Identity-Broker->Pbench-Dashboard:302 Authentication Response\n(Redirect back to Pbench dashboard)

note left of Identity-Broker:Redirect Location:\n<Pbench_dashboard_URI>\n?code=<identity_broker_auth_code>\n&state=<session_state_id>

Pbench-Dashboard->Identity-Broker:POST Request to token endpoint

note right of Pbench-Dashboard:POST request:\npost <identity_broker token endpoint>\npayload:\n{code: <identity_broker_auth_code>\nclient_id: <pbench_client_id>\nredirect_uri: <dashboard_URI>\n}

Identity-Broker->Pbench-Dashboard: 200 Token Response

note left of Identity-Broker:token response:\n{\n  access_token: <indetity_broker_access_token>,\n  expires_in: <number of seconds>,\n  refresh_expires_in: <number of seconds>,\n  refresh_token: <refresh_token>,\n  token_type: "Bearer",\n  id_token: <id_token>\n  session_state: <session_id>,\n  scope: <openid email profile>\n}

Pbench-Dashboard->Pbench-Server: POST /api/v1/<restricted_endpoint> request (Bearer: Pbench Access Token)

note over Pbench-Server:Validation and identity extraction \nfrom the Pbench token

alt case 1
Pbench-Server->Pbench-Dashboard: 200 /api/v1/<restricted_endpoint> reponse
else case 2
Pbench-Server->Pbench-Dashboard:40X /api/v1/<restricted_endpoint> reponse
end
```