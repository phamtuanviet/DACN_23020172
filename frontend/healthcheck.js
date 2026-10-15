// Healthcheck cho Docker: thoát mã 0 khi /healthz trả 200.
fetch("http://127.0.0.1:3000/healthz")
  .then((res) => process.exit(res.ok ? 0 : 1))
  .catch(() => process.exit(1));
