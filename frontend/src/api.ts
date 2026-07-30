const API_ROOT = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = body.detail ?? body.error?.message ?? `请求失败（${response.status}）`;
    throw new Error(typeof message === "string" ? message : "请求内容未通过校验");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  delete: (path: string) => request<void>(path, { method: "DELETE" }),
  upload: <T>(path: string, image: File) => {
    const data = new FormData();
    data.append("image", image);
    return request<T>(path, { method: "POST", body: data });
  },
  download: async (path: string, filename: string) => {
    const response = await fetch(`${API_ROOT}${path}`);
    if (!response.ok) throw new Error("导出失败，请稍后重试");
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  },
};
