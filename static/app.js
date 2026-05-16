localStorage.removeItem("token");
localStorage.removeItem("user");

const authStore = window.sessionStorage;

function storedUser() {
  try {
    return JSON.parse(authStore.getItem("user") || "null");
  } catch (error) {
    authStore.removeItem("user");
    return null;
  }
}

const state = {
  token: authStore.getItem("token"),
  user: storedUser(),
  authMode: "register",
  interviewId: null,
  problems: [],
  problemIndex: 0,
  jobsLoaded: false,
  recognition: null,
  listening: false,
};

const roles = [
  "Data Analyst", "Data Scientist", "Python Developer", "Frontend Developer", "Backend Developer",
  "Full Stack Developer", "SQL Developer", "HR Interview", "Behavioral Interview"
];

const $ = (id) => document.getElementById(id);

function api(path, options = {}) {
  const headers = options.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  return fetch(path, { ...options, headers: { ...headers, ...(options.headers || {}) } }).then(async (res) => {
    if (!res.ok) throw new Error((await res.json()).detail || "Request failed");
    const type = res.headers.get("content-type") || "";
    return type.includes("application/json") ? res.json() : res.text();
  });
}

function setAuth(token, user) {
  state.token = token;
  state.user = user;
  authStore.setItem("token", token);
  authStore.setItem("user", JSON.stringify(user));
  renderShell();
  refreshDashboard();
  loadProblems();
  loadHistory();
  loadJobs();
}

function renderShell() {
  document.body.classList.toggle("is-authenticated", Boolean(state.token));
  $("authView").classList.toggle("hidden", Boolean(state.token));
  $("appView").classList.toggle("hidden", !state.token);
  $("userLine").textContent = state.user ? `${state.user.name} - ${state.user.role}` : "";
}

function showView(view) {
  document.querySelectorAll(".view").forEach((el) => el.classList.add("hidden"));
  $(view).classList.remove("hidden");
  document.querySelectorAll("nav button").forEach((btn) => btn.classList.toggle("active", btn.dataset.view === view));
  $("pageTitle").textContent = document.querySelector(`[data-view="${view}"]`).textContent;
  if (view === "dashboard") refreshDashboard();
  if (view === "reports") loadHistory();
  if (view === "jobs" && !state.jobsLoaded) loadJobs();
}

function addMessage(sender, agent, content, score) {
  const div = document.createElement("div");
  div.className = `message ${sender === "Candidate" ? "candidate" : ""}`;
  div.innerHTML = `<small>${sender} - ${agent}</small><div>${escapeHtml(content)}</div>`;
  if (score) div.innerHTML += `<small>Score: ${score.overall_score}/10 - ${escapeHtml(score.feedback)}</small>`;
  $("chat").appendChild(div);
  $("chat").scrollTop = $("chat").scrollHeight;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[m]));
}

function setupVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const voiceButton = $("voiceAnswer");
  const voiceStatus = $("voiceStatus");
  if (!SpeechRecognition) {
    voiceButton.disabled = true;
    voiceButton.textContent = "No Mic";
    voiceStatus.textContent = "Voice input is not supported in this browser. Use Chrome or Edge for speech answers.";
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-IN";
  recognition.interimResults = true;
  recognition.continuous = true;
  state.recognition = recognition;

  recognition.onstart = () => {
    state.listening = true;
    voiceButton.classList.add("listening");
    voiceButton.textContent = "Stop";
    voiceStatus.textContent = "Listening...";
  };

  recognition.onend = () => {
    state.listening = false;
    voiceButton.classList.remove("listening");
    voiceButton.textContent = "Mic";
    voiceStatus.textContent = $("answerInput").value.trim() ? "Voice captured. Review and send your answer." : "";
  };

  recognition.onerror = (event) => {
    voiceStatus.textContent = `Voice input error: ${event.error}`;
  };

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = 0; i < event.results.length; i += 1) {
      transcript += event.results[i][0].transcript;
    }
    $("answerInput").value = transcript.trim();
  };

  voiceButton.addEventListener("click", () => {
    if (state.listening) {
      recognition.stop();
    } else {
      recognition.start();
    }
  });
}

async function refreshDashboard() {
  if (!state.token) return;
  const data = await api("/api/analytics");
  $("totalInterviews").textContent = data.total_interviews;
  $("averageScore").textContent = data.average_score;
  $("weakTopic").textContent = data.weak_topics[0] || (data.total_interviews ? "No weak topics yet" : "No data yet");
  $("trendChart").innerHTML = (data.trend.length ? data.trend : [0]).map((score) => `<div class="bar" style="height:${Math.max(8, score * 16)}px" title="${score}/10"></div>`).join("");
  $("roadmap").innerHTML = data.roadmap.length
    ? data.roadmap.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>Complete an interview to generate a personalized roadmap.</li>";
}

async function loadProblems() {
  const data = await api("/api/coding/problems");
  state.problems = data.problems;
  state.problemIndex = 0;
  $("problemSelect").innerHTML = data.problems.map((p, index) => (
    `<option value="${index}">${escapeHtml(p.title)} - ${escapeHtml(p.difficulty)}</option>`
  )).join("");
  selectProblem();
}

function selectProblem() {
  state.problemIndex = Number($("problemSelect").value || 0);
  const problem = state.problems[state.problemIndex] || state.problems[0];
  if (!problem) return;
  $("problemMeta").textContent = `Challenge ${state.problemIndex + 1} of ${state.problems.length} - ${problem.difficulty}`;
  $("problemPrompt").textContent = problem.prompt;
  $("codeEditor").value = problem.starter;
  $("codeOutput").textContent = "";
}

function nextProblem() {
  if (!state.problems.length) return;
  state.problemIndex = (state.problemIndex + 1) % state.problems.length;
  $("problemSelect").value = String(state.problemIndex);
  selectProblem();
}

async function loadHistory() {
  if (!state.token) return;
  const data = await api("/api/interviews");
  $("history").innerHTML = data.interviews.map((item) => `
    <div class="message">
      <small>${escapeHtml(item.created_at)} - ${escapeHtml(item.status)}</small>
      <strong>${escapeHtml(item.role)}</strong> ${escapeHtml(item.level)} at ${escapeHtml(item.company)}
      <div>Latest score: ${item.overall_score}/10</div>
    </div>
  `).join("") || "<p>No interviews yet.</p>";
}

async function loadJobs(search = "") {
  if (!state.token) return;
  $("jobStatus").textContent = "Loading live jobs...";
  $("jobsList").innerHTML = "";
  try {
    const params = search ? `?search=${encodeURIComponent(search)}` : "";
    const data = await api(`/api/jobs${params}`);
    state.jobsLoaded = true;
    $("jobSearchInput").value = search || data.query || "";
    $("jobStatus").textContent = data.error
      ? data.error
      : `${data.jobs.length} live remote jobs from ${data.source} for "${data.query}".`;
    $("jobsList").innerHTML = data.jobs.length
      ? data.jobs.map(renderJobCard).join("")
      : `<section class="card app-card p-3"><p class="mb-0">No live jobs found. Try a broader keyword like Python, data analyst, React, or SQL.</p></section>`;
  } catch (error) {
    $("jobStatus").textContent = error.message;
  }
}

function renderJobCard(job) {
  return `
    <article class="card app-card job-card p-3">
      <div>
        <small>${escapeHtml(job.category)} - ${escapeHtml(job.job_type)} - ${escapeHtml(job.published)}</small>
        <h2 class="h5">${escapeHtml(job.title)}</h2>
        <p class="job-company">${escapeHtml(job.company)}</p>
        <p class="text-secondary">${escapeHtml(job.location)} - ${escapeHtml(job.salary)}</p>
        <p>${escapeHtml(job.summary)}</p>
      </div>
      <a class="btn btn-accent" href="${escapeHtml(job.url)}" target="_blank" rel="noopener">Apply</a>
    </article>
  `;
}

document.addEventListener("DOMContentLoaded", () => {
  roles.forEach((role) => $("roleSelect").insertAdjacentHTML("beforeend", `<option>${role}</option>`));
  setupVoiceInput();
  renderShell();
  if (state.token) {
    refreshDashboard();
    loadProblems();
    loadHistory();
    loadJobs();
  }

  document.querySelectorAll("nav button").forEach((btn) => btn.addEventListener("click", () => showView(btn.dataset.view)));

  $("toggleAuth").addEventListener("click", () => {
    state.authMode = state.authMode === "register" ? "login" : "register";
    $("authTitle").textContent = state.authMode === "register" ? "Create account" : "Welcome back";
    $("name").style.display = state.authMode === "register" ? "block" : "none";
    $("accountRole").style.display = state.authMode === "register" ? "block" : "none";
    $("toggleAuth").textContent = state.authMode === "register" ? "I already have an account" : "Create a new account";
  });

  $("authForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("authError").textContent = "";
    try {
      const body = state.authMode === "register"
        ? { name: $("name").value, email: $("email").value, password: $("password").value, role: $("accountRole").value }
        : { email: $("email").value, password: $("password").value };
      const data = await api(`/api/auth/${state.authMode}`, { method: "POST", body: JSON.stringify(body) });
      setAuth(data.token, data.user);
    } catch (error) {
      $("authError").textContent = error.message;
    }
  });

  $("logoutBtn").addEventListener("click", () => {
    authStore.removeItem("token");
    authStore.removeItem("user");
    state.token = null;
    state.user = null;
    renderShell();
  });

  $("resumeForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData();
    form.append("file", $("resumeFile").files[0]);
    const data = await api("/api/resumes", { method: "POST", body: form });
    $("resumeOutput").textContent = JSON.stringify(data, null, 2);
  });

  $("startInterview").addEventListener("click", async () => {
    $("chat").innerHTML = "";
    const data = await api("/api/interviews", {
      method: "POST",
      body: JSON.stringify({
        role: $("roleSelect").value,
        level: $("levelSelect").value,
        interview_type: $("typeSelect").value,
        company: $("companySelect").value,
      }),
    });
    state.interviewId = data.id;
    addMessage("AI", data.agent, data.question);
  });

  $("answerForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.interviewId) return;
    const answer = $("answerInput").value.trim();
    if (!answer) return;
    addMessage("Candidate", "Candidate", answer);
    $("answerInput").value = "";
    const data = await api(`/api/interviews/${state.interviewId}/answer`, { method: "POST", body: JSON.stringify({ answer }) });
    addMessage("AI", data.agent, data.question, data.score);
  });

  $("finishInterview").addEventListener("click", async () => {
    if (!state.interviewId) return;
    const data = await api(`/api/interviews/${state.interviewId}/finish`, { method: "POST" });
    window.open(`${data.download_url}?token=${encodeURIComponent(state.token)}`, "_blank");
    refreshDashboard();
  });

  $("problemSelect").addEventListener("change", selectProblem);
  $("nextProblem").addEventListener("click", nextProblem);
  $("runCode").addEventListener("click", async () => {
    const problem = state.problems[state.problemIndex] || state.problems[0];
    const data = await api("/api/coding/run", {
      method: "POST",
      body: JSON.stringify({ language: $("languageSelect").value, problem_title: problem.title, code: $("codeEditor").value }),
    });
    $("codeOutput").textContent = JSON.stringify(data, null, 2);
  });

  $("jobSearchForm").addEventListener("submit", (event) => {
    event.preventDefault();
    loadJobs($("jobSearchInput").value.trim());
  });

  $("suggestJobs").addEventListener("click", () => {
    $("jobSearchInput").value = "";
    state.jobsLoaded = false;
    loadJobs();
  });
});
