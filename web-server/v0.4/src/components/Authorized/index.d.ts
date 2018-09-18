import * as ReactJS from 'react';
import { RouteProps } from 'react-router';

type authorityFN = (currentAuthority?: string) => boolean;

type authority = string | Array<string> | authorityFN | Promise<any>;

export type IReactComponent<P = any> =
  | ReactJS.StatelessComponent<P>
  | ReactJS.ComponentClass<P>
  | ReactJS.ClassicComponentClass<P>;

interface Secured {
  (authority: authority, error?: ReactJS.ReactNode): <T extends IReactComponent>(target: T) => T;
}

export interface AuthorizedRouteProps extends RouteProps {
  authority: authority;
}
export class AuthorizedRoute extends ReactJS.Component<AuthorizedRouteProps, any> {}

interface check {
  <T extends IReactComponent, S extends IReactComponent>(
    authority: authority,
    target: T,
    Exception: S
  ): T | S;
}

interface AuthorizedProps {
  authority: authority;
  noMatch?: ReactJS.ReactNode;
}

export class Authorized extends ReactJS.Component<AuthorizedProps, any> {
  static Secured: Secured;
  static AuthorizedRoute: typeof AuthorizedRoute;
  static check: check;
}

declare function renderAuthorize(currentAuthority: string): typeof Authorized;

export default renderAuthorize;
