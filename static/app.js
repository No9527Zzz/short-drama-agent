const sourceLabels = {
  idea: "创意 / 主线故事",
  complete_script: "完整剧本",
  novel: "小说原文",
};

const projectList = document.querySelector("#projects");
const form = document.querySelector("#project-form");
const message = document.querySelector("#form-message");
const health = document.querySelector("#health");

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("health check failed");
    health.textContent = "服务正常";
    health.classList.add("ok");
  } catch {
    health.textContent = "服务不可用";
  }
}

function renderProjects(projects) {
  if (!projects.length) {
    projectList.innerHTML = '<p class="muted">还没有项目，先创建第一个项目。</p>';
    return;
  }
  projectList.innerHTML = projects.map((project) => {
    const name = escapeHtml(project.name);
    const description = escapeHtml(project.description || "暂无简介");
    return '<article class="project"><div><h3>' + name + '</h3><p>' +
      sourceLabels[project.source_type] + ' · ' + description +
      '</p></div><div class="project-meta">' +
      project.target_episodes + ' 集 · ' + project.episode_duration_seconds +
      ' 秒 · ' + project.status + '</div></article>';
  }).join("");
}

async function loadProjects() {
  const response = await fetch("/api/projects");
  if (!response.ok) throw new Error("无法加载项目");
  renderProjects(await response.json());
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  message.textContent = "";
  const payload = {
    name: document.querySelector("#name").value,
    source_type: document.querySelector("#source_type").value,
    description: document.querySelector("#description").value,
  };
  try {
    const response = await fetch("/api/projects", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "创建失败");
    form.reset();
    message.style.color = "#217c48";
    message.textContent = "项目创建成功";
    await loadProjects();
  } catch (error) {
    message.style.color = "#b03a4b";
    message.textContent = error.message;
  }
});

document.querySelector("#refresh").addEventListener("click", () => loadProjects());

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

checkHealth();
loadProjects().catch((error) => {
  projectList.innerHTML = '<p class="message">' + escapeHtml(error.message) + '</p>';
});
