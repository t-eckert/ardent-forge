import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Import after mocking
const { api } = await import("./api");

function mockJsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(JSON.stringify(data)),
  };
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("api.health", () => {
  it("returns health status", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse({ status: "ok" }));
    const result = await api.health();
    expect(result).toEqual({ status: "ok" });
    expect(mockFetch).toHaveBeenCalledWith("/health", expect.any(Object));
  });
});

describe("api.listTasks", () => {
  it("fetches all tasks without filter", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse([]));
    await api.listTasks();
    expect(mockFetch).toHaveBeenCalledWith("/api/tasks", expect.any(Object));
  });

  it("fetches tasks with status filter", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse([]));
    await api.listTasks("queued");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/tasks?status=queued",
      expect.any(Object),
    );
  });
});

describe("api.createTask", () => {
  it("sends POST with task data", async () => {
    const task = {
      type: "code",
      title: "Fix bug",
      description: "Fix the login bug",
    };
    mockFetch.mockResolvedValueOnce(
      mockJsonResponse({ id: "test-id", ...task }),
    );
    await api.createTask(task);
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/tasks",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify(task),
      }),
    );
  });
});

describe("api.getTask", () => {
  it("fetches a task by ID", async () => {
    mockFetch.mockResolvedValueOnce(mockJsonResponse({ id: "abc" }));
    await api.getTask("abc");
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/tasks/abc",
      expect.any(Object),
    );
  });
});

describe("error handling", () => {
  it("throws ApiError on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      text: () => Promise.resolve("Not found"),
    });
    await expect(api.getTask("missing")).rejects.toThrow("Not found");
  });
});
