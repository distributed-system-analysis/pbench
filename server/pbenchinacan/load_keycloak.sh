#!/usr/bin/env -S bash -e

# This scripts loads the keycloak server with following configuration
# 1. A realm with the name pbench
# 2. A client pbench-client under the realm pbench
# 3. A user test_admin
# 4. An ADMIN role under the client pbench-client
# 5. ADMIN role assigned to the test_admin user.

# At the moment the Pbench-server requires a Keycloak server with at least
# no. 1 and no. 2 configuration specified above.
# This scrip assumes that Keycloak server is running and does not already have
# the configuration specified above.

KEYCLOAK_HOST_PORT=${1:-"localhost:8080"}
echo
echo "KEYCLOAK_HOST_PORT: $KEYCLOAK_HOST_PORT"

echo
echo "Getting admin access token"
echo "--------------------------"

ADMIN_TOKEN=$(curl -s -X POST "http://$KEYCLOAK_HOST_PORT/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin" \
  -d 'password=admin' \
  -d 'grant_type=password' \
  -d 'client_id=admin-cli' | jq -r '.access_token')

echo "ADMIN_TOKEN=$ADMIN_TOKEN"
echo

echo "Creating realm"
echo "--------------"

curl -i -X POST "http://$KEYCLOAK_HOST_PORT/admin/realms" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"realm": "pbench", "enabled": true}'

echo "Creating client"
echo "---------------"

CLIENT_CONF=$(curl -si -X POST "http://$KEYCLOAK_HOST_PORT/admin/realms/pbench/clients" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"clientId": "pbench-client", "directAccessGrantsEnabled": true, "serviceAccountsEnabled": true, "redirectUris": ["http://localhost:8080/*"]}')

CLIENT_ID=$(grep -o -e 'http://[^[:space:]]*' <<< $CLIENT_CONF | sed -e 's|.*/||')
echo "client_id=$CLIENT_ID"
echo

echo "Getting client secret"
echo "---------------------"

PBENCH_CLIENT_SECRET=$(curl -s -X POST "http://$KEYCLOAK_HOST_PORT/admin/realms/pbench/clients/$CLIENT_ID/client-secret" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.value')

echo "PBENCH_CLIENT_SECRET=$PBENCH_CLIENT_SECRET"
echo

echo "Creating client role"
echo "--------------------"

curl -i -X POST "http://$KEYCLOAK_HOST_PORT/admin/realms/pbench/clients/$CLIENT_ID/roles" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "ADMIN"}'

ROLE_ID=$(curl -s "http://$KEYCLOAK_HOST_PORT/admin/realms/pbench/clients/$CLIENT_ID/roles" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq -r '.[0].id')

echo "ROLE_ID=$ROLE_ID"
echo

echo "Creating user"
echo "-------------"

USER=$(curl -si -X POST "http://$KEYCLOAK_HOST_PORT/admin/realms/pbench/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username": "test_admin", "enabled": true, "credentials": [{"type": "password", "value": "123", "temporary": false}]}')

USER_ID=$(grep -o -e 'http://[^[:space:]]*' <<< $USER | sed -e 's|.*/||')
echo "USER_ID=$USER_ID"
echo

echo "Setting client role to user"
echo "---------------------------"

curl -i -X POST "http://$KEYCLOAK_HOST_PORT/admin/realms/pbench/users/$USER_ID/role-mappings/clients/$CLIENT_ID" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[{"id":"'"$ROLE_ID"'","name":"ADMIN"}]'

echo "Getting user access token"
echo "-------------------------"

curl -s -X POST "http://$KEYCLOAK_HOST_PORT/realms/pbench/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test_admin" \
  -d "password=123" \
  -d "grant_type=password" \
  -d "client_secret=$PBENCH_CLIENT_SECRET" \
  -d "client_id=pbench-client" | jq -r .access_token
echo

echo "---------"
echo "PBENCH_CLIENT_SECRET=$PBENCH_CLIENT_SECRET"
echo "---------"