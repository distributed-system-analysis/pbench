import request from '../utils/request';

// queies all the available shared sessions from the database to display
export async function querySharedSessions(params) {
  const { datastoreConfig } = params;

  const endpoint = `${datastoreConfig.graphql}`;

  return request.post(endpoint, {
    data: {
      query: `
        query {
          urls {
              id
              config
              description
              createdAt
          }   
        }`,
    },
  });
}

// Updates the description of shared session, provided by the user in the database.
export async function updateDescription(params) {
  const { datastoreConfig, id, value } = params;

  const endpoint = `${datastoreConfig.graphql}`;

  return request.post(endpoint, {
    data: {
      query: `
        mutation($description: String!,$id: ID!) {
        updateUrl(
          data: {description: $description}
          where: {id: $id})
        {
          id
          config
          description
        }
      }`,
      variables: {
        id,
        description: value,
      },
    },
  });
}
