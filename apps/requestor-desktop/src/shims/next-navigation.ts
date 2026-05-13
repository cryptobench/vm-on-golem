import { useMemo } from "react";
import {
  useLocation,
  useNavigate,
  useSearchParams as useRouterSearchParams,
} from "react-router-dom";

export function useRouter() {
  const navigate = useNavigate();
  return useMemo(
    () => ({
      push: (href: string) => navigate(href),
      replace: (href: string) => navigate(href, { replace: true }),
      back: () => navigate(-1),
      forward: () => navigate(1),
      refresh: () => undefined,
      prefetch: () => Promise.resolve(),
    }),
    [navigate],
  );
}

export function usePathname() {
  return useLocation().pathname;
}

export function useSearchParams() {
  const [params] = useRouterSearchParams();
  return params;
}
