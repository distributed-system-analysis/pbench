import moment from 'moment';
import axios from 'axios';

function parseMonths(datastoreConfig, startMonth, endMonth) {
  let months = '/';

  if (endMonth.isBefore(moment().endOf('month'))) {
    months = months.concat(
      ',' + datastoreConfig.run_index + datastoreConfig.prefix + endMonth.format('YYYY-MM') + ','
    );
  }
  while (startMonth.isBefore(endMonth) && startMonth.isBefore(moment().endOf('month'))) {
    months = months.concat(
      ',' + datastoreConfig.run_index + datastoreConfig.prefix + startMonth.format('YYYY-MM') + ','
    );
    startMonth.add(1, 'month');
  }

  return months;
}

export async function queryIndexMapping(params) {
  const { datastoreConfig, startMonth, endMonth } = params;

  const endpoint = datastoreConfig.elasticsearch + '/_cluster/state/metadata/' + datastoreConfig.prefix + datastoreConfig.run_index + startMonth.format('YYYY-MM') + '?human';

  return request(endpoint, {
    method: 'GET'
  });
}

export async function searchQuery(params) {
  const { datastoreConfig, startMonth, endMonth, query } = params;

  const endpoint = datastoreConfig.elasticsearch + parseMonths(datastoreConfig, startMonth, endMonth) + '/_search';

  return request(endpoint, {
    method: 'POST',
    body: {
      query: {
          query_string: {
              analyze_wildcard: true,
              query: query
          }
      }
    }
  });
}