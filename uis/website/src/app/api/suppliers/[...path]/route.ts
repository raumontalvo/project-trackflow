const BACKEND_URL = "http://127.0.0.1:8000";

type Params = {
  params: Promise<{
    path: string[];
  }>;
};

function errorResponse(message: string, status = 502) {
  return Response.json({ detail: message }, { status });
}

async function proxy(request: Request, params: Params["params"]) {
  try {
    const resolvedParams = await params;
    const path = "/" + resolvedParams.path.join("/");
    const { search } = new URL(request.url);
    const body = request.method === "GET" ? undefined : await request.text();

    const res = await fetch(`${BACKEND_URL}/suppliers${path}${search}`, {
      method: request.method,
      headers: {
        "Content-Type": "application/json",
      },
      body,
      cache: "no-store",
    });

    const data = await res.text();

    return new Response(data, {
      status: res.status,
      headers: {
        "Content-Type": "application/json",
      },
    });
  } catch {
    return errorResponse(
      "The supplier service is currently unavailable. Please try again later."
    );
  }
}

export async function GET(request: Request, { params }: Params) {
  return proxy(request, params);
}

export async function PATCH(request: Request, { params }: Params) {
  return proxy(request, params);
}

export async function DELETE(request: Request, { params }: Params) {
  return proxy(request, params);
}