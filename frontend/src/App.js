import React, { useState, useEffect } from "react";
import { API_BASE_URL } from "./config";

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("posts");

  // Close sidebar when switching tabs on mobile
  const handleTabChange = (tab) => {
    setActiveTab(tab);
    if (window.innerWidth < 768) {
      setSidebarOpen(false);
    }
  };

  // Close sidebar when clicking outside on mobile
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (window.innerWidth < 768 && sidebarOpen) {
        const sidebar = document.querySelector("[data-sidebar]");
        const menuButton = document.querySelector("[data-menu-button]");
        if (
          sidebar &&
          !sidebar.contains(event.target) &&
          menuButton &&
          !menuButton.contains(event.target)
        ) {
          setSidebarOpen(false);
        }
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [sidebarOpen]);

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
    <div className="flex h-screen bg-gray-50">
      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        data-sidebar
        className={`fixed z-30 inset-y-0 left-0 w-64 transform ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        } transition-transform duration-300 ease-in-out bg-gray-900 text-white md:translate-x-0 md:static md:z-auto`}
      >
        <div className="flex items-center justify-center h-16 border-b border-gray-700 px-4">
          <h1 className="text-xl font-bold truncate">⚽ KickOffZone</h1>
        </div>
        <nav className="mt-6 space-y-1">
          {[
            { id: "posts", label: "Posts", icon: "📰" },
            { id: "upload", label: "Manual Upload", icon: "📤" },
            { id: "birthdays", label: "Birthdays", icon: "🎂" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`flex items-center w-full text-left px-4 py-3 text-sm transition-colors ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white"
                  : "text-gray-300 hover:bg-gray-800 hover:text-white"
              }`}
            >
              <span className="mr-3 text-base">{tab.icon}</span>
              <span className="truncate">{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Main content */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Navbar */}
        <header className="flex items-center justify-between bg-white shadow-sm border-b border-gray-200 px-4 py-3 md:px-6">
          <button
            data-menu-button
            className="md:hidden p-2 rounded-md text-gray-600 hover:bg-gray-100 transition-colors"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            <span className="text-xl">☰</span>
          </button>
          <h2 className="text-lg font-semibold text-gray-800 truncate md:text-xl">
            {activeTab === "posts" && "All Posts"}
            {activeTab === "upload" && "Manual Upload"}
            {activeTab === "birthdays" && "Birthday Generator"}
          </h2>
          <div className="w-8 md:w-auto"></div> {/* Spacer for balance */}
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6">
          {renderContent()}
        </main>
      </div>
    </div>
  );
}

export default App;

//
// ---------- 1️⃣ Posts Page (Improved) ----------
//
function PostsPage() {
  const [posts, setPosts] = useState([]);
  const [status, setStatus] = useState("draft");
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState({});
  const [selectedPosts, setSelectedPosts] = useState([]);
  const [fetchingNews, setFetchingNews] = useState(false);

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

  const handleAction = async (id, endpoint, actionName) => {
    setActionLoading((prev) => ({ ...prev, [id]: actionName }));
    try {
      await fetch(`${API_BASE_URL}/${endpoint}/${id}`, { method: "POST" });
      setPosts((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      console.error("Action failed:", err);
      alert(`${actionName} failed. Please try again.`);
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  const handleBulkReject = async () => {
    if (selectedPosts.length === 0) return;

    if (
      !window.confirm(
        `Reject ${selectedPosts.length} selected post${
          selectedPosts.length > 1 ? "s" : ""
        }?`
      )
    )
      return;

    try {
      await Promise.all(
        selectedPosts.map((id) =>
          fetch(`${API_BASE_URL}/reject/${id}`, { method: "POST" })
        )
      );
      setPosts((prev) => prev.filter((p) => !selectedPosts.includes(p.id)));
      setSelectedPosts([]);
    } catch (err) {
      alert("Bulk reject failed. Please try again.");
    }
  };

  const handleFetchNews = async () => {
    setFetchingNews(true);
    try {
      await fetch(`${API_BASE_URL}/fetch_news`, { method: "POST" });
      await loadPosts(status);
    } catch (err) {
      alert("Failed to fetch latest news.");
    } finally {
      setFetchingNews(false);
    }
  };

  const toggleSelect = (id) => {
    setSelectedPosts((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedPosts.length === posts.length) {
      setSelectedPosts([]);
    } else {
      setSelectedPosts(posts.map((p) => p.id));
    }
  };

  return (
    <div className="space-y-4">
      {/* Sticky Header Controls */}
      <div className="sticky top-0 z-20 bg-white/95 backdrop-blur-sm shadow-sm border-b border-gray-200 p-4">
        <div className="flex flex-col gap-3">
          {/* Status Filter */}
          <div className="flex flex-wrap gap-2">
            {["draft", "approved", "published"].map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  status === s
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap gap-2 items-center">
            <button
              onClick={handleFetchNews}
              disabled={fetchingNews}
              className="px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {fetchingNews ? (
                <>
                  <span className="animate-spin">⟳</span>
                  Fetching...
                </>
              ) : (
                "🔄 Fetch Latest News"
              )}
            </button>

            {status === "draft" && posts.length > 0 && (
              <div className="flex items-center gap-2 ml-auto">
                {selectedPosts.length > 0 && (
                  <span className="text-sm text-gray-600 whitespace-nowrap">
                    {selectedPosts.length} selected
                  </span>
                )}
                <button
                  onClick={toggleSelectAll}
                  className="px-3 py-2 rounded-lg border border-gray-300 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  {selectedPosts.length === posts.length
                    ? "Deselect All"
                    : "Select All"}
                </button>
                {selectedPosts.length > 0 && (
                  <button
                    onClick={handleBulkReject}
                    className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 transition-colors"
                  >
                    Reject Selected
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Posts Grid */}
      <div className="p-2 md:p-0">
        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : posts.length === 0 ? (
          <div className="text-center py-12 text-gray-500 bg-white rounded-lg border border-gray-200">
            <div className="text-4xl mb-3">📭</div>
            <p className="text-lg">No {status} posts found.</p>
            {status === "draft" && (
              <button
                onClick={handleFetchNews}
                className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Fetch News
              </button>
            )}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {posts.map((post) => {
              const isSelected = selectedPosts.includes(post.id);
              const isLoading = actionLoading[post.id];

              return (
                <div
                  key={post.id}
                  className={`relative bg-white rounded-xl shadow-sm hover:shadow-md transition-all duration-200 border ${
                    isSelected
                      ? "border-blue-500 ring-2 ring-blue-500 ring-opacity-20"
                      : "border-gray-200"
                  }`}
                >
                  {status === "draft" && (
                    <div className="absolute top-3 left-3 z-10">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(post.id)}
                        className="h-5 w-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                    </div>
                  )}

                  {post.image && (
                    <div className="relative h-48 bg-gray-100 rounded-t-xl overflow-hidden">
                      <img
                        src={`${API_BASE_URL}/${post.image}`}
                        alt={post.title}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.target.style.display = "none";
                          e.target.nextSibling.style.display = "flex";
                        }}
                      />
                      <div className="absolute inset-0 hidden items-center justify-center bg-gray-100">
                        <span className="text-gray-400">📷</span>
                      </div>
                    </div>
                  )}

                  <div className="p-4">
                    <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2 leading-tight">
                      {post.title}
                    </h3>
                    <p className="text-sm text-gray-600 mb-4 line-clamp-3 leading-relaxed">
                      {post.summary || "No summary available"}
                    </p>

                    <div className="flex flex-wrap gap-2">
                      {status === "draft" && (
                        <>
                          <button
                            disabled={!!isLoading}
                            onClick={() =>
                              handleAction(post.id, "approve", "Approve")
                            }
                            className="flex-1 min-w-[80px] px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                          >
                            {isLoading === "Approve" ? "..." : "Approve"}
                          </button>
                          <button
                            disabled={!!isLoading}
                            onClick={() =>
                              handleAction(post.id, "reject", "Reject")
                            }
                            className="flex-1 min-w-[80px] px-3 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 disabled:opacity-50 transition-colors"
                          >
                            {isLoading === "Reject" ? "..." : "Reject"}
                          </button>
                        </>
                      )}
                      {status === "approved" && (
                        <>
                          <button
                            disabled={!!isLoading}
                            onClick={() =>
                              handleAction(post.id, "publish", "Publish")
                            }
                            className="flex-1 min-w-[80px] px-3 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
                          >
                            {isLoading === "Publish" ? "..." : "Publish"}
                          </button>
                          <button
                            disabled={!!isLoading}
                            onClick={() =>
                              handleAction(post.id, "reject", "Reject")
                            }
                            className="flex-1 min-w-[80px] px-3 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 disabled:opacity-50 transition-colors"
                          >
                            {isLoading === "Reject" ? "..." : "Reject"}
                          </button>
                        </>
                      )}
                    </div>
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
// ---------- 2️⃣ Manual Upload (Improved) ----------
//
function ManualUpload() {
  const [formData, setFormData] = useState({
    title: "",
    summary: "",
    image: null,
    postNow: false,
    scheduleLater: false,
    scheduledTime: "",
  });
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleInputChange = (field, value) => {
    setFormData((prev) => {
      // Handle mutual exclusivity for postNow and scheduleLater
      if (field === "postNow" && value) {
        return { ...prev, [field]: value, scheduleLater: false };
      }
      if (field === "scheduleLater" && value) {
        return { ...prev, [field]: value, postNow: false };
      }
      return { ...prev, [field]: value };
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.title || !formData.image) {
      alert("Please provide a title and image.");
      return;
    }

    const submitData = new FormData();
    submitData.append("title", formData.title);
    submitData.append("summary", formData.summary);
    submitData.append("image", formData.image);
    submitData.append("post_now", formData.postNow);

    if (formData.scheduleLater && formData.scheduledTime) {
      const formatted = new Date(formData.scheduledTime).toISOString();
      submitData.append("scheduled_time", formatted);
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/upload_manual_post`, {
        method: "POST",
        body: submitData,
      });
      const data = await res.json();
      alert(data.message || "Post created successfully!");

      // Reset form
      setFormData({
        title: "",
        summary: "",
        image: null,
        postNow: false,
        scheduleLater: false,
        scheduledTime: "",
      });
      setPreview(null);
    } catch (err) {
      alert("Error uploading post. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
        <div className="bg-gradient-to-r from-blue-600 to-blue-700 px-6 py-4">
          <h3 className="text-xl font-semibold text-white">
            📤 Upload a Manual Post
          </h3>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Title *
            </label>
            <input
              type="text"
              placeholder="Enter post title..."
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
              value={formData.title}
              onChange={(e) => handleInputChange("title", e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Summary
            </label>
            <textarea
              placeholder="Enter post summary (optional)..."
              rows={4}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors resize-none"
              value={formData.summary}
              onChange={(e) => handleInputChange("summary", e.target.value)}
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Image *
            </label>
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-4 text-center hover:border-gray-400 transition-colors">
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const file = e.target.files[0];
                  handleInputChange("image", file);
                  if (file) {
                    setPreview(URL.createObjectURL(file));
                  }
                }}
                className="hidden"
                id="image-upload"
                required
              />
              <label htmlFor="image-upload" className="cursor-pointer block">
                <div className="text-gray-500 mb-2">
                  {formData.image ? "Change image" : "Click to upload image"}
                </div>
                {!formData.image && <div className="text-4xl mb-2">📁</div>}
              </label>
            </div>
          </div>

          {preview && (
            <div className="flex justify-center">
              <img
                src={preview}
                alt="Preview"
                className="max-w-full h-48 object-cover rounded-lg shadow-sm"
              />
            </div>
          )}

          <div className="space-y-4 p-4 bg-gray-50 rounded-lg">
            <label className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors cursor-pointer">
              <input
                type="checkbox"
                checked={formData.postNow}
                onChange={(e) => handleInputChange("postNow", e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <div>
                <div className="font-medium text-gray-900">
                  Post to Facebook immediately
                </div>
                <div className="text-sm text-gray-500">
                  Publish this post right away
                </div>
              </div>
            </label>

            <label className="flex items-center gap-3 p-3 bg-white rounded-lg border border-gray-200 hover:bg-gray-50 transition-colors cursor-pointer">
              <input
                type="checkbox"
                checked={formData.scheduleLater}
                onChange={(e) =>
                  handleInputChange("scheduleLater", e.target.checked)
                }
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <div>
                <div className="font-medium text-gray-900">
                  Schedule Facebook post
                </div>
                <div className="text-sm text-gray-500">
                  Set a future publishing time
                </div>
              </div>
            </label>

            {formData.scheduleLater && (
              <div className="pl-11">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Schedule Date & Time
                </label>
                <input
                  type="datetime-local"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                  value={formData.scheduledTime}
                  onChange={(e) =>
                    handleInputChange("scheduledTime", e.target.value)
                  }
                  required
                />
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Uploading...
              </>
            ) : formData.scheduleLater ? (
              "📅 Schedule Post"
            ) : formData.postNow ? (
              "🚀 Post Now"
            ) : (
              "💾 Save Draft"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

//
// ---------- 3️⃣ Birthday Generator (Improved) ----------
//
function BirthdayGenerator() {
  const [birthdays, setBirthdays] = useState([]);
  const [status, setStatus] = useState("draft");
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [actionLoading, setActionLoading] = useState({});

  const loadBirthdays = async (s) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/birthdays?status=${s}`);
      const data = await res.json();
      setBirthdays(data);
    } catch (err) {
      console.error("Error fetching birthdays:", err);
      alert("Failed to load birthday posts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBirthdays(status);
  }, [status]);

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

  const handleAction = async (id, action, endpoint) => {
    if (!window.confirm(`${action} this post?`)) return;

    setActionLoading((prev) => ({ ...prev, [id]: action }));
    try {
      const res = await fetch(
        `${API_BASE_URL}/api/birthdays/${id}/${endpoint}`,
        {
          method: action === "Delete" ? "DELETE" : "POST",
        }
      );
      const data = await res.json();

      if (data.message) {
        if (action === "Approve")
          alert("Post approved and published to Facebook!");
        loadBirthdays(status);
      } else {
        alert(data.error || `${action} failed`);
      }
    } catch (err) {
      alert(`${action} failed. Please try again.`);
      console.error(err);
    } finally {
      setActionLoading((prev) => ({ ...prev, [id]: false }));
    }
  };

  return (
    <div className="space-y-4">
      {/* Header controls */}
      <div className="sticky top-0 z-20 bg-white/95 backdrop-blur-sm shadow-sm border-b border-gray-200 p-4">
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-2">
            {["draft", "approved", "rejected"].map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  status === s
                    ? "bg-blue-600 text-white shadow-sm"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-green-600 to-green-700 text-white text-sm font-medium hover:from-green-700 hover:to-green-800 disabled:opacity-50 transition-colors flex items-center gap-2 w-fit"
          >
            {generating ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                Generating...
              </>
            ) : (
              "🎂 Generate Today's Birthdays"
            )}
          </button>
        </div>
      </div>

      {/* Posts Grid */}
      <div className="p-2 md:p-0">
        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          </div>
        ) : birthdays.length === 0 ? (
          <div className="text-center py-12 text-gray-500 bg-white rounded-lg border border-gray-200">
            <div className="text-4xl mb-3">🎂</div>
            <p className="text-lg">No {status} birthday posts found.</p>
            {status === "draft" && (
              <button
                onClick={handleGenerate}
                className="mt-3 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                Generate Posts
              </button>
            )}
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {birthdays.map((b) => {
              const isLoading = actionLoading[b.id];

              return (
                <div
                  key={b.id}
                  className="bg-white rounded-xl shadow-sm hover:shadow-md transition-all duration-200 border border-gray-200"
                >
                  {b.image_path && (
                    <div className="relative h-48 bg-gray-100 rounded-t-xl overflow-hidden">
                      <img
                        src={`${API_BASE_URL}/${b.image_path}`}
                        alt={b.name}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.target.style.display = "none";
                          e.target.nextSibling.style.display = "flex";
                        }}
                      />
                      <div className="absolute inset-0 hidden items-center justify-center bg-gray-100">
                        <span className="text-gray-400">🎂</span>
                      </div>
                    </div>
                  )}

                  <div className="p-4">
                    <h3 className="font-semibold text-gray-900 text-lg mb-1">
                      {b.name}
                    </h3>
                    <p className="text-sm text-gray-600 mb-1">{b.team}</p>
                    {b.age && (
                      <p className="text-xs text-gray-500 mb-3">Age: {b.age}</p>
                    )}

                    <div className="flex flex-wrap gap-2">
                      {status === "draft" && (
                        <>
                          <button
                            onClick={() =>
                              handleAction(b.id, "Approve", "approve")
                            }
                            disabled={isLoading}
                            className="flex-1 min-w-[80px] px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                          >
                            {isLoading === "Approve" ? "..." : "Approve"}
                          </button>
                          <button
                            onClick={() =>
                              handleAction(b.id, "Reject", "reject")
                            }
                            disabled={isLoading}
                            className="flex-1 min-w-[80px] px-3 py-2 bg-red-500 text-white text-sm font-medium rounded-lg hover:bg-red-600 disabled:opacity-50 transition-colors"
                          >
                            {isLoading === "Reject" ? "..." : "Reject"}
                          </button>
                        </>
                      )}
                      {status !== "draft" && (
                        <button
                          onClick={() => handleAction(b.id, "Delete", "delete")}
                          disabled={isLoading}
                          className="w-full px-3 py-2 bg-gray-500 text-white text-sm font-medium rounded-lg hover:bg-gray-600 disabled:opacity-50 transition-colors"
                        >
                          {isLoading === "Delete" ? "..." : "Delete"}
                        </button>
                      )}
                    </div>
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
