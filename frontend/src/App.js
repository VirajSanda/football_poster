import React, { useState, useEffect } from "react";
import { API_BASE_URL } from "./config";

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("posts");

  // Reusable tab switcher
  const renderContent = () => {
    switch (activeTab) {
      case "posts":
        return <PostsPage />;
      case "upload":
        return <ManualUpload />;
      case "birthdays":
        return <BirthdayGenerator />;
      default:
        return <PostsPage />;
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <div
        className={`fixed z-30 inset-y-0 left-0 w-64 transform ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } transition-transform duration-200 ease-in-out bg-gray-900 text-white md:translate-x-0`}
      >
        <div className="flex items-center justify-center h-16 border-b border-gray-700">
          <h1 className="text-2xl font-bold">⚽ KickOffZone</h1>
        </div>
        <nav className="mt-6">
          <button
            onClick={() => setActiveTab("posts")}
            className={`block w-full text-left px-6 py-3 hover:bg-gray-800 ${
              activeTab === "posts" ? "bg-gray-800" : ""
            }`}
          >
            📰 Posts
          </button>
          <button
            onClick={() => setActiveTab("upload")}
            className={`block w-full text-left px-6 py-3 hover:bg-gray-800 ${
              activeTab === "upload" ? "bg-gray-800" : ""
            }`}
          >
            📤 Manual Upload
          </button>
          <button
            onClick={() => setActiveTab("birthdays")}
            className={`block w-full text-left px-6 py-3 hover:bg-gray-800 ${
              activeTab === "birthdays" ? "bg-gray-800" : ""
            }`}
          >
            🎂 Birthdays
          </button>
        </nav>
      </div>

      {/* Main content */}
      <div className="flex flex-col flex-1 md:ml-64">
        {/* Navbar */}
        <header className="flex items-center justify-between bg-white shadow px-4 py-3">
          <button
            className="md:hidden text-gray-700"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            ☰
          </button>
          <h2 className="text-xl font-semibold text-gray-800">
            {activeTab === "posts"
              ? "All Posts"
              : activeTab === "upload"
              ? "Manual Upload"
              : "Birthday Generator"}
          </h2>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-6">{renderContent()}</main>
      </div>
    </div>
  );
}

export default App;

//
// ---------- 1️⃣ Posts Page ----------
//
function PostsPage() {
  const [posts, setPosts] = useState([]);
  const [status, setStatus] = useState("draft");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState({});
  const [selectedPosts, setSelectedPosts] = useState([]);

  const loadPosts = async (s) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/posts?status=${s}`);
      const data = await res.json();
      setPosts(data);
      setSelectedPosts([]);
    } catch (err) {
      console.error("Error fetching posts:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPosts(status);
  }, [status]);

  const handleAction = async (id, endpoint) => {
    setActionLoading((prev) => ({ ...prev, [id]: true }));
    try {
      await fetch(`${API_BASE_URL}/${endpoint}/${id}`, { method: "POST" });
      setPosts((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      console.error("Action failed:", err);
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const handleBulkReject = async () => {
    if (selectedPosts.length === 0) {
      alert("Select at least one post to reject.");
      return;
    }
    if (!window.confirm(`Reject ${selectedPosts.length} posts?`)) return;

    for (const id of selectedPosts) {
      await fetch(`${API_BASE_URL}/reject/${id}`, { method: "POST" });
    }

    setPosts((prev) => prev.filter((p) => !selectedPosts.includes(p.id)));
    setSelectedPosts([]);
  };

  const toggleSelect = (id) => {
    setSelectedPosts((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  return (
    <div className="relative">
      {/* Sticky Header Controls */}
      <div className="sticky top-0 z-30 bg-white/90 backdrop-blur-sm shadow-sm border-b border-gray-200 p-3 flex flex-wrap gap-2 items-center">
        {/* Status Filter Buttons */}
        {["draft", "approved", "published"].map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`px-4 py-2 rounded font-medium ${
              status === s
                ? "bg-blue-600 text-white"
                : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            {s.toUpperCase()}
          </button>
        ))}

        {/* Fetch News */}
        <button
          onClick={() =>
            fetch(`${API_BASE_URL}/fetch_news`, { method: "POST" }).then(() =>
              loadPosts(status)
            )
          }
          className="px-4 py-2 rounded bg-green-600 text-white hover:bg-green-700"
        >
          Fetch Latest News
        </button>

        {/* Bulk Reject (only visible for draft) */}
        {status === "draft" && selectedPosts.length > 0 && (
          <button
            onClick={handleBulkReject}
            className="ml-auto px-4 py-2 rounded bg-red-600 text-white hover:bg-red-700"
          >
            Reject Selected ({selectedPosts.length})
          </button>
        )}
      </div>

      {/* Posts Grid */}
      <div className="p-4">
        {loading ? (
          <div className="text-center py-8 text-gray-600">Loading...</div>
        ) : posts.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No {status} posts found.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {posts.map((post) => {
              const isSelected = selectedPosts.includes(post.id);
              const isLoading = actionLoading[post.id];

              return (
                <div
                  key={post.id}
                  className={`relative bg-white rounded-lg shadow hover:shadow-lg transition p-4 ${
                    isSelected ? "ring-2 ring-blue-500" : ""
                  }`}
                >
                  {status === "draft" && (
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(post.id)}
                      className="absolute top-3 left-3 h-5 w-5 accent-blue-600"
                    />
                  )}

                  {post.image && (
                    <img
                      src={`${API_BASE_URL}/${post.image}`}
                      alt={post.title}
                      className="w-full h-48 object-cover rounded-md mb-3"
                    />
                  )}
                  <h3 className="font-semibold text-lg mb-1">{post.title}</h3>
                  <p className="text-sm text-gray-600 mb-2 line-clamp-3">
                    {post.summary}
                  </p>

                  <div className="flex gap-2 mt-2">
                    {status === "draft" && (
                      <>
                        <button
                          disabled={isLoading}
                          onClick={() => handleAction(post.id, "approve")}
                          className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                        >
                          {isLoading ? "..." : "Approve"}
                        </button>
                        <button
                          disabled={isLoading}
                          onClick={() => handleAction(post.id, "reject")}
                          className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
                        >
                          {isLoading ? "..." : "Reject"}
                        </button>
                      </>
                    )}
                    {status === "approved" && (
                      <>
                        <button
                          disabled={isLoading}
                          onClick={() => handleAction(post.id, "publish")}
                          className="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
                        >
                          {isLoading ? "..." : "Publish"}
                        </button>
                        <button
                          disabled={isLoading}
                          onClick={() => handleAction(post.id, "reject")}
                          className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
                        >
                          {isLoading ? "..." : "Reject"}
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

//
// ---------- 2️⃣ Manual Upload ----------
//
function ManualUpload() {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [image, setImage] = useState(null);
  const [preview, setPreview] = useState(null);
  const [postNow, setPostNow] = useState(false);
  const [scheduleLater, setScheduleLater] = useState(false);
  const [scheduledTime, setScheduledTime] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title || !image) {
      alert("Please provide a title and image.");
      return;
    }

    const formData = new FormData();
    formData.append("title", title);
    formData.append("summary", summary);
    formData.append("image", image);
    formData.append("post_now", postNow);

    if (scheduleLater && scheduledTime) {
      // backend supports ISO or 'YYYY-MM-DD HH:mm'
      const formatted = new Date(scheduledTime).toISOString();
      formData.append("scheduled_time", formatted);
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/upload_manual_post`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      alert(data.message || "Post created!");
      setTitle("");
      setSummary("");
      setImage(null);
      setPreview(null);
      setPostNow(false);
      setScheduleLater(false);
      setScheduledTime("");
    } catch (err) {
      alert("Error uploading post.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-lg mx-auto bg-white p-6 rounded-lg shadow">
      <h3 className="text-xl font-semibold mb-4">📤 Upload a Manual Post</h3>

      <form onSubmit={handleSubmit} className="space-y-4">
        <input
          type="text"
          placeholder="Title"
          className="w-full border rounded px-3 py-2"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />

        <textarea
          placeholder="Summary (optional)"
          className="w-full border rounded px-3 py-2"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />

        <input
          type="file"
          accept="image/*"
          onChange={(e) => {
            const file = e.target.files[0];
            setImage(file);
            if (file) {
              setPreview(URL.createObjectURL(file));
            }
          }}
        />

        {preview && (
          <img
            src={preview}
            alt="Preview"
            className="w-full h-48 object-cover rounded-md mt-2"
          />
        )}

        <div className="flex flex-col gap-2 mt-4">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={postNow}
              disabled={scheduleLater}
              onChange={(e) => setPostNow(e.target.checked)}
            />
            Post to Facebook immediately
          </label>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={scheduleLater}
              disabled={postNow}
              onChange={(e) => setScheduleLater(e.target.checked)}
            />
            Schedule Facebook post
          </label>

          {scheduleLater && (
            <input
              type="datetime-local"
              className="w-full border rounded px-3 py-2"
              value={scheduledTime}
              onChange={(e) => setScheduledTime(e.target.value)}
              required
            />
          )}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700"
        >
          {loading
            ? "Uploading..."
            : scheduleLater
            ? "Schedule Post"
            : postNow
            ? "Post Now"
            : "Save Draft"}
        </button>
      </form>
    </div>
  );
}

//
// ---------- 3️⃣ Birthday Generator + Approval ----------
//
function BirthdayGenerator() {
  const [birthdays, setBirthdays] = useState([]);
  const [status, setStatus] = useState("draft");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Load birthday posts by status
  const loadBirthdays = async (s) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/birthdays?status=${s}`);
      const data = await res.json();
      setBirthdays(data);
    } catch (err) {
      console.error("Error fetching birthdays:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBirthdays(status);
  }, [status]);

  // Generate new birthday posts
  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/birthdays/generate`, {
        method: "POST",
      });
      const data = await res.json();
      alert(data.message || "Generated today's birthday posts!");
      loadBirthdays(status);
    } catch (err) {
      alert("Error generating birthday posts.");
      console.error(err);
    } finally {
      setGenerating(false);
    }
  };

  // Approve a post (auto-posts to Facebook)
  const handleApprove = async (id) => {
    if (!window.confirm("Approve and post to Facebook?")) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/birthdays/${id}/approve`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.message) alert(data.message);
      else alert(data.error || "Approval failed");
      loadBirthdays(status);
    } catch (err) {
      console.error(err);
      alert("Approval failed.");
    }
  };

  // Reject a post
  const handleReject = async (id) => {
    if (!window.confirm("Reject this post?")) return;
    try {
      await fetch(`${API_BASE_URL}/api/birthdays/${id}/reject`, {
        method: "POST",
      });
      loadBirthdays(status);
    } catch (err) {
      console.error(err);
      alert("Reject failed.");
    }
  };

  // Delete post
  const handleDelete = async (id) => {
    if (!window.confirm("Delete this post permanently?")) return;
    try {
      await fetch(`${API_BASE_URL}/api/birthdays/${id}/delete`, {
        method: "DELETE",
      });
      loadBirthdays(status);
    } catch (err) {
      console.error(err);
      alert("Delete failed.");
    }
  };

  return (
    <div className="relative">
      {/* Header controls */}
      <div className="sticky top-0 z-30 bg-white/90 backdrop-blur-sm shadow-sm border-b border-gray-200 p-3 flex flex-wrap gap-2 items-center">
        {["draft", "approved", "rejected"].map((s) => (
          <button
            key={s}
            onClick={() => setStatus(s)}
            className={`px-4 py-2 rounded font-medium ${
              status === s
                ? "bg-blue-600 text-white"
                : "bg-gray-100 hover:bg-gray-200"
            }`}
          >
            {s.toUpperCase()}
          </button>
        ))}

        <button
          onClick={handleGenerate}
          disabled={generating}
          className="ml-auto px-4 py-2 rounded bg-green-600 text-white hover:bg-green-700"
        >
          {generating ? "Generating..." : "Generate Today’s Birthdays"}
        </button>
      </div>

      {/* Posts Grid */}
      <div className="p-4">
        {loading ? (
          <div className="text-center py-8 text-gray-600">Loading...</div>
        ) : birthdays.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No {status} birthday posts found.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {birthdays.map((b) => (
              <div
                key={b.id}
                className="bg-white rounded-lg shadow hover:shadow-lg transition p-4 relative"
              >
                {b.image_path && (
                  <img
                    src={`${API_BASE_URL}/${b.image_path}`}
                    alt={b.name}
                    className="w-full h-48 object-cover rounded-md mb-3"
                  />
                )}
                <h3 className="font-semibold text-lg mb-1">{b.name}</h3>
                <p className="text-sm text-gray-600 mb-2">{b.team}</p>

                <div className="flex gap-2 mt-2">
                  {status === "draft" && (
                    <>
                      <button
                        onClick={() => handleApprove(b.id)}
                        className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleReject(b.id)}
                        className="px-3 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
                      >
                        Reject
                      </button>
                    </>
                  )}
                  {status !== "draft" && (
                    <button
                      onClick={() => handleDelete(b.id)}
                      className="px-3 py-1 bg-gray-500 text-white rounded hover:bg-gray-600 text-sm"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
