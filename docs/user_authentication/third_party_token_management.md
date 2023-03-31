
```sequence {theme: 'simple'}
title Third-party Token Management

participant Pbench-Server
participant Browser
participant Identity-Broker
participant Identity-Provider

autonumber 1
activate Browser #red

rbox over Browser: Dashboard
Browser->Pbench-Server: GET Pbench client ID

Pbench-Server->Browser: 200 Response 

note right of Pbench-Server:{identity_broker_auth_URI: <auth_URI>\nclient_id: <pbench_client_id>\nclient_secret: <pbench_client_secret> # optional\n}

note over Browser:User clicks login
abox over Browser: Dashboard instructs the browser to \nload identity broker authentication page \nurl that was supplied by the Pbench-server.

deactivate Browser

Browser->Identity-Broker:GET identity broker auth URI\n(Authentication Request)

note right of Browser:GET request:\n<identity_broker_auth_URI>\n?client_id=<pbench_client_id>\n&response_type=code\n&redirect_uri=<dashboard_URI>\n&scope=openid

Identity-Broker->Browser: 200 Response

activate Browser #blue
rbox over Browser: Identity-Broker
note over Browser:User selects an identity provider from the list

abox over Browser:Identity broker instructs the browser to \nload identity provider authentication page

deactivate Browser

Browser->Identity-Provider:GET identity provider auth page
note over Browser:Ref: https://openid.net/specs/openid-connect-core-1_0.html#AuthorizationEndpoint
note right of Browser:GET request:\n<identity_provider_auth_URI>\n?client_id=<client_id as registered on identity provider>\n&response_type=code\n&redirect_uri=<identity_broker_URI>\n&scope=openid

Identity-Provider->Browser:303 Response\n(Redirect to identity provider auth page)

Browser->Identity-Provider:GET request auth Page
Browser<-Identity-Provider:200 Response

activate Browser #green
rbox over Browser: Identity-Provider

note over Browser:User challenge credentials and consent

abox over Browser:Identity provider instructs the browser to \nsend the request and load the response

deactivate Browser

Browser->Identity-Provider: GET/POST authentication request

Identity-Provider->Browser: 302/303 Response
note left of Identity-Provider:Redirect Location:\n<identity_broker_URI>\n?code=<auth_code>\n&state=<session_state_id>

Identity-Broker<-Browser:GET Redirect location (identity broker URI)

note over Identity-Broker:Identity federation\na. Checks the validity of response from the identity provider\nb. Imports and creates user identity from the token\nc. Links the user identity with the identity provider

Identity-Broker->Browser:302 Authentication Response\n(Redirect back to Pbench dashboard)

note left of Identity-Broker:Redirect Location:\n<dashboard_URI>\n?code=<identity_broker_auth_code>\n&state=<session_state_id>

Browser->Pbench-Server: GET Pbench-dashboard redirect location

Pbench-Server->Browser: 200 Response

activate Browser #red
rbox over Browser: Dashboard

Browser->Identity-Broker:POST Request to token endpoint

note right of Browser:POST request:\npost <identity_broker_token_endpoint>\npayload:\n{code: <identity_broker_auth_code>\nclient_id: <pbench_client_id>\nredirect_uri: <dashboard_URI>\n}

Identity-Broker->Browser: 200 Token Response

note left of Identity-Broker:token response:\n{\n  access_token: <identity_broker_access_token>,\n  expires_in: <number_of_seconds>,\n  refresh_expires_in: <number_of_seconds>,\n  refresh_token: <refresh_token>,\n  token_type: "Bearer",\n  id_token: <id_token>\n  session_state: <session_id>,\n  scope: <openid_email_profile>\n}

==Authorization setup complete; the steps below may be repeated to issue a series of requests==

Browser->Pbench-Server: POST /api/v1/<restricted_endpoint> request (Bearer: Pbench access token)

note over Pbench-Server:Validation and identity extraction\nfrom the Pbench token

alt Authenticated user is authorized for resource
Pbench-Server->Browser: 200 /api/v1/<restricted_endpoint> response
else Authenticated user is not authorized for resource
Pbench-Server->Browser:403 /api/v1/<restricted_endpoint> response
else Authorization token expired or invalid
Pbench-Server->Browser:401 /api/v1/<restricted_endpoint> response
end

space 
deactivate Browser
destroysilent Pbench-Server
destroysilent Browser
destroysilent Identity-Broker
destroysilent Identity-Provider
```