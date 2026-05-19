import React from "react";
import { getPriceUSD, onPricesUpdated } from "@golem/prices";

export function useGlmUsdPrice() {
  const [price, setPrice] = React.useState(() => getPriceUSD("GLM"));

  React.useEffect(() => {
    const update = () => setPrice(getPriceUSD("GLM"));
    update();
    return onPricesUpdated(update);
  }, []);

  return price;
}

export function glmToUsd(glm: number | null | undefined, glmUsd: number | null) {
  if (glm == null || glmUsd == null || !Number.isFinite(glm) || !Number.isFinite(glmUsd)) {
    return null;
  }
  return glm * glmUsd;
}

export function usdToGlm(usd: number | null | undefined, glmUsd: number | null) {
  if (usd == null || glmUsd == null || !Number.isFinite(usd) || !Number.isFinite(glmUsd) || glmUsd <= 0) {
    return null;
  }
  return usd / glmUsd;
}
