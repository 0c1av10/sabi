module.exports = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.BACKEND_URL || "https://sabi-api.vercel.app"}/api/:path*` }];
  },
};
