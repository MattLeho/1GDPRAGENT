/** @type {import('next').NextConfig} */
const nextConfig = {
  // The graph ontology is deliberately shared with backend tooling at the
  // repository root. Make that boundary explicit for Turbopack as well as the
  // configured Webpack commands.
  turbopack: {
    root: '..',
  },
};

export default nextConfig;
