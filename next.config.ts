import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  htmlLimitedBots: /.*/, // Resolve metadata before hydration can apply the selected language.
};

export default nextConfig;
