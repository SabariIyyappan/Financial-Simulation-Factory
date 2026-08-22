// Thin REST client for Port. Auth + entity upsert only — no business logic.
// API reference: https://docs.port.io/api-reference

export interface PortConfig {
  clientId: string;
  clientSecret: string;
  baseUrl?: string;
}

interface CachedToken {
  token: string;
  expiresAt: number;
}

export class PortClient {
  private readonly baseUrl: string;
  private cached: CachedToken | null = null;

  constructor(private readonly config: PortConfig) {
    this.baseUrl = (config.baseUrl ?? process.env.PORT_API_BASE ?? "https://api.getport.io").replace(
      /\/$/,
      ""
    );
  }

  static fromEnv(): PortClient {
    const clientId = process.env.PORT_CLIENT_ID;
    const clientSecret = process.env.PORT_CLIENT_SECRET;
    if (!clientId || !clientSecret) {
      throw new Error(
        "PORT_CLIENT_ID and PORT_CLIENT_SECRET must be set. Port → Settings → Credentials."
      );
    }
    return new PortClient({ clientId, clientSecret });
  }

  private async token(): Promise<string> {
    if (this.cached && this.cached.expiresAt > Date.now()) return this.cached.token;

    const res = await fetch(`${this.baseUrl}/v1/auth/access_token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientId: this.config.clientId,
        clientSecret: this.config.clientSecret,
      }),
    });
    if (!res.ok) {
      throw new Error(`Port auth failed: HTTP ${res.status} ${await res.text()}`);
    }
    const data = (await res.json()) as { accessToken: string; expiresIn?: number };
    // Refresh a minute early rather than racing the real expiry mid-workflow.
    const ttlMs = (data.expiresIn ?? 3600) * 1000 - 60_000;
    this.cached = { token: data.accessToken, expiresAt: Date.now() + ttlMs };
    return data.accessToken;
  }

  async request<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${await this.token()}`,
        ...init.headers,
      },
    });
    const text = await res.text();
    if (!res.ok) {
      throw new Error(`Port ${init.method ?? "GET"} ${path} failed: HTTP ${res.status} ${text}`);
    }
    return (text ? JSON.parse(text) : {}) as T;
  }

  async upsertEntity(
    blueprint: string,
    entity: {
      identifier: string;
      title?: string;
      properties?: Record<string, unknown>;
      relations?: Record<string, string | string[] | null>;
    }
  ) {
    return this.request(`/v1/blueprints/${blueprint}/entities?upsert=true&merge=true`, {
      method: "POST",
      body: JSON.stringify(entity),
    });
  }

  async getEntity<T = unknown>(blueprint: string, identifier: string): Promise<T> {
    return this.request<T>(`/v1/blueprints/${blueprint}/entities/${identifier}`);
  }

  async createBlueprint(definition: unknown) {
    return this.request(`/v1/blueprints`, {
      method: "POST",
      body: JSON.stringify(definition),
    });
  }

  async createScorecard(blueprint: string, definition: unknown) {
    return this.request(`/v1/blueprints/${blueprint}/scorecards`, {
      method: "POST",
      body: JSON.stringify(definition),
    });
  }
}
