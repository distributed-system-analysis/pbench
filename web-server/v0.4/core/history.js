import createBrowserHistory from 'history/lib/createBrowserHistory';
import useQueries from 'history/lib/useQueries';

export default useQueries(createBrowserHistory)();
