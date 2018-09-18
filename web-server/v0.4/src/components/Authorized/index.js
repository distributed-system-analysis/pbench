import Authorized from 'components/Authorized/Authorized';
import AuthorizedRoute from 'components/Authorized/AuthorizedRoute';
import Secured from 'components/Authorized/Secured';
import check from 'components/Authorized/CheckPermissions';
import renderAuthorize from 'components/Authorized/renderAuthorize';

Authorized.Secured = Secured;
Authorized.AuthorizedRoute = AuthorizedRoute;
Authorized.check = check;

export default renderAuthorize(Authorized);
