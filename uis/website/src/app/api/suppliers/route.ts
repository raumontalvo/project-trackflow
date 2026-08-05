const BACKEND_URL = "http://127.0.0.1:8000";

async function proxy(request: Request, path = "") {
  const { search } = new URL(request.url);

  const res = await fetch(`${BACKEND_URL}/suppliers${path}${search}`, {
    method: request.method,
    headers: {
      "Content-Type": "application/json",
    },
    body: request.method === "GET" ? undefined : await request.text(),
    cache: "no-store",
  });

  const data = await res.text();

  return new Response(data, {
    status: res.status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

export async function GET(request: Request) {
  return proxy(request);
}

export async function POST(request: Request) {
  return proxy(request);
}