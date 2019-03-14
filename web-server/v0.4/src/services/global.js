import request from '../utils/request';

export async function saveUserSession(params) {
  const { sessionConfig, description, datastoreConfig } = params;
  return request.post(datastoreConfig.graphql, {
    data: {
      query: `
            mutation($config: String!, $description: String!) {
              createUrl(data: {config: $config, description: $description}) {
                id
                config
                description
              }
            }       
          `,
      variables: {
        config: sessionConfig,
        description,
      },
    },
  });
}

export async function queryUserSession(params) {
  const { id, datastoreConfig } = params;
  return request.post(datastoreConfig.graphql, {
    data: {
      query: `
        query($id: ID!) {
            url(where: {id: $id}) {
                id
                config
                description
            }
      }`,
      variables: {
        id,
      },
    },
  });
}
