import React from "react";
import { Link as RouterLink, type LinkProps as RouterLinkProps } from "react-router-dom";

type NextLinkProps = Omit<RouterLinkProps, "to"> & {
  href: RouterLinkProps["to"];
};

const Link = React.forwardRef<HTMLAnchorElement, NextLinkProps>(
  ({ href, ...props }, ref) => <RouterLink ref={ref} to={href} {...props} />,
);

Link.displayName = "NextLinkShim";

export default Link;
