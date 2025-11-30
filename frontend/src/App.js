import { useState, useEffect } from "react";
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
      case "videos":
        return <VideoUploadPage />;
      case "birthdays":
        return <BirthdayGenerator />;
      case "missing-images": // Add this new case
        return <PostsWithoutImages />;
      case "scheduled":
        return <ScheduledPostsManager />;
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
            { id: "videos", label: "Video Upload", icon: "🎥" },
            { id: "birthdays", label: "Birthdays", icon: "🎂" },
            { id: "missing-images", label: "Missing Images", icon: "📸" },
            { id: "scheduled", label: "Scheduled Posts", icon: "📅" }, // Add this new tab
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
            {activeTab === "videos" && "Video Upload"}
            {activeTab === "birthdays" && "Birthday Generator"}
            {activeTab === "missing-images" && "Missing Images"}
            {activeTab === "scheduled" && "Scheduled"}
          </h2>
          <div className="w-8 md:w-auto"></div> {/* Spacer for balance */}
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-2 md:p-2">
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
// ---------- 4️⃣ YouTube Video Upload Page ----------
//
function VideoUploadPage() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);

  const handleUpload = async () => {
    if (!file) {
      setResult({ ok: false, error: "Please select a video file first." });
      return;
    }

    setUploading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/upload_video`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setResult({ ok: false, error: err.message });
    }

    setUploading(false);
  };

  return (
    <div className="max-w-xl mx-auto bg-white shadow-md p-6 rounded-lg">
      <h3 className="text-xl font-semibold mb-4">Upload Video to YouTube</h3>

      {/* File Picker */}
      <input
        type="file"
        accept="video/*"
        onChange={(e) => setFile(e.target.files[0])}
        className="w-full border p-2 rounded mb-4"
      />

      {/* Upload Button */}
      <button
        onClick={handleUpload}
        disabled={uploading}
        className={`w-full py-3 rounded text-white font-medium ${
          uploading ? "bg-gray-500" : "bg-blue-600 hover:bg-blue-700"
        }`}
      >
        {uploading ? "Uploading..." : "Upload Video"}
      </button>

      {/* Result Message */}
      {result && (
        <div
          className={`mt-4 p-3 rounded ${
            result.ok
              ? "bg-green-100 text-green-800"
              : "bg-red-100 text-red-800"
          }`}
        >
          {result.ok ? (
            <div>
              ✅ Uploaded Successfully! <br />
            </div>
          ) : (
            <>❌ {result.error}</>
          )}
        </div>
      )}
    </div>
  );
}

//
// ---------- 3️⃣ Birthday Generator (Improved) ----------
//
function BirthdayGenerator() {
  const [birthdays, setBirthdays] = useState([]);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState(null);
  const [uploads, setUploads] = useState({});
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [selectedBirthday, setSelectedBirthday] = useState(null);
  const [scheduleTime, setScheduleTime] = useState("");

  // Load today's birthdays
  const loadBirthdays = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/birthday_posts`);
      const data = await res.json();
      setBirthdays(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("❌ Error loading:", err);
      alert("Failed to load birthday posts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBirthdays();
  }, []);

  // Convert local datetime to UTC ISO string
  const convertLocalToUTC = (localDateTime) => {
    if (!localDateTime) return null;

    // Create a Date object from local time
    const localDate = new Date(localDateTime);

    // Convert to UTC ISO string
    return localDate.toISOString();
  };

  // Format the display time for user confirmation
  const formatDisplayTime = (utcTime) => {
    return new Date(utcTime).toLocaleString();
  };

  // Open schedule modal
  const openScheduleModal = (b) => {
    setSelectedBirthday(b);
    setScheduleTime("");
    setShowScheduleModal(true);
  };

  // Close schedule modal
  const closeScheduleModal = () => {
    setShowScheduleModal(false);
    setSelectedBirthday(null);
    setScheduleTime("");
  };

  // Approve & Post (with optional scheduling)
  const handleApprovePost = async (scheduledTime = null) => {
    if (!selectedBirthday) return;

    setProcessingId(selectedBirthday.id);

    try {
      const formData = new FormData();
      formData.append("name", selectedBirthday.name);
      formData.append("year", selectedBirthday.birth_year || "");
      formData.append("post_id", selectedBirthday.id || "");

      // Add scheduled time if provided (already in UTC)
      if (scheduledTime) {
        formData.append("scheduled_time", scheduledTime);
      }

      // attach uploaded images
      if (
        uploads[selectedBirthday.id] &&
        uploads[selectedBirthday.id].length > 0
      ) {
        uploads[selectedBirthday.id].forEach((f) =>
          formData.append("images", f)
        );
      } else {
        formData.append("image_urls", selectedBirthday.image);
      }

      const res = await fetch(`${API_BASE_URL}/birthday_post_direct`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (data.success) {
        const message = scheduledTime
          ? `Scheduled ${selectedBirthday.name} for ${formatDisplayTime(
              scheduledTime
            )}!`
          : `Posted ${selectedBirthday.name} successfully!`;

        alert(message);
        setBirthdays((prev) =>
          prev.filter((x) => x.id !== selectedBirthday.id)
        );
        closeScheduleModal();
      } else {
        alert(`Failed: ${data.error}`);
      }
    } catch (err) {
      alert("Server error posting.");
    } finally {
      setProcessingId(null);
    }
  };

  // Post immediately
  const handlePostNow = () => {
    handleApprovePost(null); // No scheduled time = post immediately
  };

  // Post with schedule
  const handlePostScheduled = () => {
    if (!scheduleTime) {
      alert("Please select a schedule time");
      return;
    }

    // Convert local time to UTC for backend
    const utcTime = convertLocalToUTC(scheduleTime);
    handleApprovePost(utcTime);
  };

  // Reject
  const handleReject = async (b) => {
    setProcessingId(b.id);
    try {
      await fetch(`${API_BASE_URL}/reject_post/${b.id}`, { method: "POST" });
      setBirthdays((prev) => prev.filter((x) => x.id !== b.id));
    } catch (e) {
      alert("Error rejecting.");
    } finally {
      setProcessingId(null);
    }
  };

  // Calculate min datetime (current local time + 10 minutes)
  const getMinDateTime = () => {
    const now = new Date();
    now.setMinutes(now.getMinutes() + 10); // Minimum 10 minutes from now

    // Format for datetime-local input (YYYY-MM-DDTHH:MM)
    return now.toISOString().slice(0, 16);
  };

  // Calculate max datetime (end of today in local time)
  const getMaxDateTime = () => {
    const endOfToday = new Date();
    endOfToday.setHours(23, 59, 59, 999); // End of today

    // Format for datetime-local input
    return endOfToday.toISOString().slice(0, 16);
  };

  return (
    <div className="space-y-4">
      {/* Schedule Modal */}
      {showScheduleModal && selectedBirthday && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl p-6 w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">
              Schedule Post for {selectedBirthday.name}
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Schedule Time (Your Local Time)
                </label>
                <input
                  type="datetime-local"
                  value={scheduleTime}
                  onChange={(e) => setScheduleTime(e.target.value)}
                  min={getMinDateTime()}
                  max={getMaxDateTime()}
                  className="w-full p-2 border border-gray-300 rounded-lg"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Leave empty to post immediately. Minimum 10 minutes from now.
                  {scheduleTime && (
                    <span className="block mt-1 text-blue-600 font-medium">
                      Will post at:{" "}
                      {formatDisplayTime(convertLocalToUTC(scheduleTime))}
                    </span>
                  )}
                </p>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={handlePostNow}
                  disabled={processingId === selectedBirthday.id}
                  className="flex-1 bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 disabled:bg-blue-300"
                >
                  {processingId === selectedBirthday.id
                    ? "Posting..."
                    : "Post Now"}
                </button>

                {scheduleTime && (
                  <button
                    onClick={handlePostScheduled}
                    disabled={processingId === selectedBirthday.id}
                    className="flex-1 bg-purple-600 text-white py-2 rounded-lg hover:bg-purple-700 disabled:bg-purple-300"
                  >
                    {processingId === selectedBirthday.id
                      ? "Scheduling..."
                      : "Schedule"}
                  </button>
                )}
              </div>

              <button
                onClick={closeScheduleModal}
                disabled={processingId === selectedBirthday.id}
                className="w-full bg-gray-500 text-white py-2 rounded-lg hover:bg-gray-600 disabled:bg-gray-300"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="p-4 flex justify-between items-center bg-white shadow">
        <h2 className="text-lg font-semibold">
          🎂 Today's Celebrity Birthdays
        </h2>
        <button
          onClick={loadBirthdays}
          disabled={loading}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg"
        >
          {loading ? "Loading..." : "🔄 Refresh"}
        </button>
      </div>

      {loading ? (
        <div className="text-center py-12">Loading…</div>
      ) : birthdays.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          No birthdays for today.
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 p-2">
          {birthdays.map((b) => (
            <div
              key={b.id}
              className="bg-white rounded-xl border shadow-sm p-4 flex flex-col"
            >
              <img
                src={
                  b.image.startsWith("http")
                    ? b.image
                    : `${API_BASE_URL}${b.image}`
                }
                alt={b.name}
                className="w-full h-52 object-contain bg-gray-100 rounded-lg"
              />

              <h3 className="mt-3 text-lg font-semibold">{b.name}</h3>
              <p className="text-sm text-gray-600 mb-3">
                Born {b.birth_year || "N/A"}
              </p>

              {/* Multiple Upload */}
              <input
                type="file"
                multiple
                accept="image/*"
                onChange={(e) => {
                  const files = Array.from(e.target.files);
                  setUploads((prev) => ({ ...prev, [b.id]: files }));
                }}
                className="text-sm border p-1 rounded-md mb-2"
              />

              {uploads[b.id] && uploads[b.id].length > 0 && (
                <div className="flex gap-2 overflow-x-auto">
                  {uploads[b.id].map((file, i) => (
                    <div key={i} className="relative">
                      <img
                        src={URL.createObjectURL(file)}
                        alt="birthday"
                        className="w-16 h-16 rounded border object-cover"
                      />
                      <button
                        onClick={() =>
                          setUploads((prev) => ({
                            ...prev,
                            [b.id]: prev[b.id].filter((_, idx) => idx !== i),
                          }))
                        }
                        className="absolute top-0 right-0 text-xs bg-red-600 text-white rounded-full px-1"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => openScheduleModal(b)}
                  disabled={processingId === b.id}
                  className="flex-1 bg-green-600 text-white py-2 rounded-lg hover:bg-green-700"
                >
                  ✅ Approve
                </button>

                <button
                  onClick={() => handleReject(b)}
                  disabled={processingId === b.id}
                  className="flex-1 bg-red-600 text-white py-2 rounded-lg hover:bg-red-700"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

//
// ---------- 4️⃣ Missing Images Viewer ----------
//
function PostsWithoutImages() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [uploadType, setUploadType] = useState("file");
  const [activePost, setActivePost] = useState(null);

  const fetchPosts = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_BASE_URL}/api/posts/without-images`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        setPosts(data.posts);
      } else {
        setError(data.error || "Failed to load posts");
      }
    } catch (err) {
      console.error("Error fetching posts:", err);
      setError(`Failed to load posts: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPosts();
  }, []);

  const uploadImage = async (postId, formData) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/posts/${postId}/upload-image`,
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("Upload error:", error);
      return { success: false, error: error.message };
    }
  };

  const setImageUrl = async (postId, imageUrl) => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/posts/${postId}/set-image-url`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ image_url: imageUrl }),
        }
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error("URL set error:", error);
      return { success: false, error: error.message };
    }
  };

  const handleFileUpload = async (postId, file) => {
    if (!file) {
      alert("Please select an image file");
      return;
    }

    const formData = new FormData();
    formData.append("image", file);

    const result = await uploadImage(postId, formData);

    if (result.success) {
      alert("✅ Image uploaded successfully!");
      fetchPosts(); // Refresh the list
    } else {
      alert("❌ Upload failed: " + result.error);
    }
  };

  const handleUrlSubmit = async (postId, url) => {
    if (!url.trim()) {
      alert("Please enter an image URL");
      return;
    }

    const result = await setImageUrl(postId, url.trim());

    if (result.success) {
      alert("✅ Image URL set successfully!");
      fetchPosts(); // Refresh the list
    } else {
      alert("❌ Failed to set image URL: " + result.error);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "Not scheduled";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Debug: Check what error we're getting
  useEffect(() => {
    if (error) {
      console.log("Current error state:", error);
    }
  }, [error]);

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <div className="text-red-600 text-lg mr-3">❌</div>
            <div>
              <h3 className="text-red-800 font-medium">Error loading posts</h3>
              <p className="text-red-600 text-sm mt-1">{error}</p>
              <p className="text-red-500 text-xs mt-2">
                API Endpoint: {API_BASE_URL}/api/posts/without-images
              </p>
            </div>
          </div>
          <button
            onClick={fetchPosts}
            className="mt-3 bg-red-600 text-white px-4 py-2 rounded text-sm hover:bg-red-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6">
      {/* Header Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{posts.length}</div>
          <div className="text-gray-600 text-sm">Total Posts</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-orange-600">
            {posts.length}
          </div>
          <div className="text-gray-600 text-sm">Need Images</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-green-600">
            {posts.filter((p) => p.scheduled_time).length}
          </div>
          <div className="text-gray-600 text-sm">Scheduled</div>
        </div>
      </div>

      {/* Posts List */}
      {posts.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
          <div className="text-6xl mb-4">🎉</div>
          <h3 className="text-xl font-semibold text-gray-800 mb-2">
            All caught up!
          </h3>
          <p className="text-gray-600">No posts without images found.</p>
          <p className="text-gray-500 text-sm mt-1">
            All scheduled posts have images ready for Facebook.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {posts.map((post) => (
            <div
              key={post.id}
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6"
            >
              {/* Post Header */}
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-3 mb-4">
                <h3 className="text-lg font-semibold text-gray-800 flex-1">
                  {post.title}
                </h3>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">
                    {post.source}
                  </span>
                  <span className="text-gray-500 text-sm">
                    {formatDate(post.created_at)}
                  </span>
                </div>
              </div>

              {/* Post Summary */}
              {post.summary && (
                <p className="text-gray-600 mb-4 leading-relaxed">
                  {post.summary}
                </p>
              )}

              {/* Post URL */}
              <a
                href={post.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-600 hover:text-blue-800 text-sm mb-4 inline-block break-all"
              >
                🔗 {post.url}
              </a>

              {/* Scheduled Time */}
              {post.scheduled_time && (
                <div className="flex items-center text-orange-600 text-sm mb-4">
                  <span className="mr-2">📅</span>
                  Scheduled: {formatDate(post.scheduled_time)}
                </div>
              )}

              {/* Upload Section */}
              <div className="border-t border-gray-200 pt-4">
                <div className="flex flex-wrap gap-2 mb-4">
                  <button
                    onClick={() => {
                      setUploadType("file");
                      setActivePost(post.id);
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      uploadType === "file" && activePost === post.id
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    📁 Upload File
                  </button>
                  <button
                    onClick={() => {
                      setUploadType("url");
                      setActivePost(post.id);
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      uploadType === "url" && activePost === post.id
                        ? "bg-blue-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    }`}
                  >
                    🔗 Set URL
                  </button>
                </div>

                {activePost === post.id && (
                  <div className="space-y-3">
                    {uploadType === "file" ? (
                      <FileUploadSection
                        post={post}
                        onUpload={handleFileUpload}
                      />
                    ) : (
                      <UrlUploadSection
                        post={post}
                        onSubmit={handleUrlSubmit}
                      />
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Refresh Button */}
      <div className="fixed bottom-6 right-6">
        <button
          onClick={fetchPosts}
          className="bg-blue-600 text-white p-3 rounded-full shadow-lg hover:bg-blue-700 transition-colors"
          title="Refresh posts"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}

// Sub-component for file upload
function FileUploadSection({ post, onUpload }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(selectedFile);
    }
  };

  const handleSubmit = async () => {
    if (!file) {
      alert("Please select an image file");
      return;
    }

    setUploading(true);
    await onUpload(post.id, file);
    setUploading(false);
    setFile(null);
    setPreview(null);
  };

  return (
    <div className="space-y-3">
      <input
        type="file"
        accept="image/png, image/jpeg, image/gif, image/webp"
        onChange={handleFileChange}
        className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
      />

      {preview && (
        <div className="mt-2">
          <p className="text-sm text-gray-600 mb-2">Preview:</p>
          <img
            src={preview}
            alt="Preview"
            className="max-w-xs rounded-lg border border-gray-300"
          />
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={!file || uploading}
        className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        {uploading ? (
          <span className="flex items-center">
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            Uploading...
          </span>
        ) : (
          "📤 Upload Image"
        )}
      </button>
    </div>
  );
}

// Sub-component for URL upload
function UrlUploadSection({ post, onSubmit }) {
  const [url, setUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    await onSubmit(post.id, url);
    setSubmitting(false);
    setUrl("");
  };

  return (
    <div className="space-y-3">
      <input
        type="url"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://example.com/image.jpg"
        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      />

      <button
        onClick={handleSubmit}
        disabled={!url.trim() || submitting}
        className="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        {submitting ? (
          <span className="flex items-center">
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            Setting URL...
          </span>
        ) : (
          "✅ Set Image URL"
        )}
      </button>
    </div>
  );
}

//
// ---------- 5️⃣ Scheduled Posts Manager ----------
//
function ScheduledPostsManager() {
  const [posts, setPosts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(null);

  const fetchScheduledPosts = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(`${API_BASE_URL}/api/scheduled-posts`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        setPosts(data.posts);
      } else {
        setError(data.error || "Failed to load scheduled posts");
      }
    } catch (err) {
      console.error("Error fetching scheduled posts:", err);
      setError(`Failed to load scheduled posts: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchScheduledPosts();
  }, []);

  const cancelSchedule = async (postId) => {
    if (
      !window.confirm(
        "Remove this post from the scheduled queue? It will stay in the database but won't be posted to Facebook."
      )
    ) {
      return;
    }

    try {
      setActionLoading(postId);
      const response = await fetch(
        `${API_BASE_URL}/api/posts/${postId}/cancel-schedule`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const data = await response.json();

      if (data.success) {
        alert("✅ Post removed from scheduled queue");
        fetchScheduledPosts(); // Refresh the list
      } else {
        alert("❌ Failed to cancel schedule: " + data.error);
      }
    } catch (err) {
      alert("❌ Error canceling schedule: " + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const deletePost = async (postId) => {
    if (
      !window.confirm(
        "Are you sure you want to permanently delete this post? This action cannot be undone."
      )
    ) {
      return;
    }

    try {
      setActionLoading(postId);
      const response = await fetch(
        `${API_BASE_URL}/api/posts/${postId}/delete`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      const data = await response.json();

      if (data.success) {
        alert("✅ Post deleted permanently");
        fetchScheduledPosts(); // Refresh the list
      } else {
        alert("❌ Failed to delete post: " + data.error);
      }
    } catch (err) {
      alert("❌ Error deleting post: " + err.message);
    } finally {
      setActionLoading(null);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "Not scheduled";
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getTimeUntilPost = (scheduledTime) => {
    const now = new Date();
    const scheduled = new Date(scheduledTime);
    const diffMs = scheduled - now;
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffMinutes = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

    if (diffMs < 0) {
      return "Should post now";
    } else if (diffHours < 1) {
      return `in ${diffMinutes} minutes`;
    } else if (diffHours < 24) {
      return `in ${diffHours} hours`;
    } else {
      const diffDays = Math.floor(diffHours / 24);
      return `in ${diffDays} days`;
    }
  };

  const getStatusColor = (scheduledTime) => {
    const scheduled = new Date(scheduledTime);
    const now = new Date();
    const oneHourFromNow = new Date(now.getTime() + 60 * 60 * 1000);

    if (scheduled <= now) {
      return "text-red-600 bg-red-100"; // Overdue
    } else if (scheduled <= oneHourFromNow) {
      return "text-orange-600 bg-orange-100"; // Soon
    } else {
      return "text-green-600 bg-green-100"; // Future
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center">
            <div className="text-red-600 text-lg mr-3">❌</div>
            <div>
              <h3 className="text-red-800 font-medium">
                Error loading scheduled posts
              </h3>
              <p className="text-red-600 text-sm mt-1">{error}</p>
            </div>
          </div>
          <button
            onClick={fetchScheduledPosts}
            className="mt-3 bg-red-600 text-white px-4 py-2 rounded text-sm hover:bg-red-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          Scheduled Posts Review
        </h1>
        <p className="text-gray-600">
          Review posts scheduled for Facebook. Remove any posts that don't meet
          quality standards.
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-blue-600">{posts.length}</div>
          <div className="text-gray-600 text-sm">Total Scheduled</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-green-600">
            {
              posts.filter((p) => new Date(p.scheduled_time) > new Date())
                .length
            }
          </div>
          <div className="text-gray-600 text-sm">Future Posts</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-red-600">
            {
              posts.filter((p) => new Date(p.scheduled_time) <= new Date())
                .length
            }
          </div>
          <div className="text-gray-600 text-sm">Ready to Post</div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 text-center">
          <div className="text-2xl font-bold text-purple-600">
            {posts.filter((p) => p.image_url).length}
          </div>
          <div className="text-gray-600 text-sm">With Images</div>
        </div>
      </div>

      {/* Posts List */}
      {posts.length === 0 ? (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
          <div className="text-6xl mb-4">📅</div>
          <h3 className="text-xl font-semibold text-gray-800 mb-2">
            No scheduled posts
          </h3>
          <p className="text-gray-600">
            There are no posts scheduled for posting.
          </p>
          <p className="text-gray-500 text-sm mt-1">
            Run the scraper to find and schedule new posts.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {posts.map((post) => (
            <div
              key={post.id}
              className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 md:p-6"
            >
              <div className="flex flex-col md:flex-row gap-4">
                {/* Post Image */}
                {post.image_url && (
                  <div className="flex-shrink-0">
                    <img
                      src={
                        post.image_url.startsWith("/")
                          ? `${API_BASE_URL}${post.image_url}`
                          : post.image_url
                      }
                      alt={post.title}
                      className="w-32 h-24 object-cover rounded-lg border border-gray-200"
                      onError={(e) => {
                        e.target.style.display = "none";
                      }}
                    />
                  </div>
                )}

                {/* Post Content */}
                <div className="flex-1 min-w-0">
                  {/* Post Header */}
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-3 mb-3">
                    <h3 className="text-lg font-semibold text-gray-800 flex-1">
                      {post.title}
                    </h3>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(
                          post.scheduled_time
                        )}`}
                      >
                        {getTimeUntilPost(post.scheduled_time)}
                      </span>
                      <span className="bg-blue-100 text-blue-800 text-xs px-2 py-1 rounded-full">
                        {post.source}
                      </span>
                      {!post.image_url && (
                        <span className="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded-full">
                          No Image
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Post Summary */}
                  {post.summary && (
                    <p className="text-gray-600 mb-3 leading-relaxed">
                      {post.summary}
                    </p>
                  )}

                  {/* Schedule Info */}
                  <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600 mb-3">
                    <div className="flex items-center">
                      <span className="mr-2">📅</span>
                      <span className="font-medium">
                        {formatDate(post.scheduled_time)}
                      </span>
                    </div>
                  </div>

                  {/* Post URL */}
                  <a
                    href={post.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 text-sm inline-block break-all"
                  >
                    🔗 {post.url}
                  </a>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="border-t border-gray-200 mt-4 pt-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => cancelSchedule(post.id)}
                    disabled={actionLoading === post.id}
                    className="bg-orange-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-orange-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                  >
                    {actionLoading === post.id ? (
                      <span className="flex items-center">
                        <svg
                          className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                          fill="none"
                          viewBox="0 0 24 24"
                        >
                          <circle
                            className="opacity-25"
                            cx="12"
                            cy="12"
                            r="10"
                            stroke="currentColor"
                            strokeWidth="4"
                          ></circle>
                          <path
                            className="opacity-75"
                            fill="currentColor"
                            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                          ></path>
                        </svg>
                        Processing...
                      </span>
                    ) : (
                      "⏸️ Remove from Queue"
                    )}
                  </button>

                  <button
                    onClick={() => deletePost(post.id)}
                    disabled={actionLoading === post.id}
                    className="bg-red-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                  >
                    🗑️ Delete Permanently
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-2">
                  "Remove from Queue" keeps the post in database but stops it
                  from being posted. "Delete Permanently" removes it completely.
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Refresh Button */}
      <div className="fixed bottom-6 right-6">
        <button
          onClick={fetchScheduledPosts}
          className="bg-blue-600 text-white p-3 rounded-full shadow-lg hover:bg-blue-700 transition-colors"
          title="Refresh scheduled posts"
        >
          <svg
            className="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
