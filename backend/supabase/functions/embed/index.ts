const model = new Supabase.ai.Session("gte-small");

Deno.serve(async (request) => {
  if (request.method !== "POST") {
    return Response.json({ error: "Method not allowed" }, { status: 405 });
  }

  const expectedSecret = Deno.env.get("EMBEDDING_API_SECRET");
  const providedSecret = request.headers.get("x-embedding-secret");
  if (!expectedSecret || providedSecret !== expectedSecret) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  try {
    const payload = await request.json();
    const input = typeof payload.input === "string" ? payload.input.trim() : "";
    if (!input || input.length > 10_000) {
      return Response.json(
        { error: "Input must contain between 1 and 10000 characters" },
        { status: 422 },
      );
    }

    const result = await model.run(input, {
      mean_pool: true,
      normalize: true,
    });
    const embedding = Array.from(result);
    return Response.json({
      embedding,
      dimensions: embedding.length,
      model: "gte-small",
    });
  } catch (error) {
    console.error("Embedding generation failed", error);
    return Response.json(
      { error: "Embedding generation failed" },
      { status: 500 },
    );
  }
});
