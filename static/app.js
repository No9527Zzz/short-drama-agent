const sourceLabels = {
  idea: "创意 / 主线故事",
  complete_script: "完整剧本",
  novel: "小说原文",
};
const statusLabels = { draft: "草稿", review: "待审核", approved: "已确认" };
let selectedProject = null;
let selectedEpisode = null;

const projectList = document.querySelector("#projects");
const form = document.querySelector("#project-form");
const health = document.querySelector("#health");
const workspace = document.querySelector("#workspace");
const planning = document.querySelector("#planning");
const editor = document.querySelector("#episode-editor");

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error();
    health.textContent = "服务正常";
    health.classList.add("ok");
  } catch {
    health.textContent = "服务不可用";
  }
}

async function loadProjects() {
  const response = await fetch("/api/projects");
  if (!response.ok) throw new Error("无法加载项目");
  const projects = await response.json();
  if (!projects.length) {
    projectList.innerHTML = '<p class="muted">还没有项目，先创建第一个项目。</p>';
    return;
  }
  projectList.innerHTML = projects.map((project) => {
    const active = selectedProject && selectedProject.id === project.id ? " active" : "";
    return '<article class="project' + active + '" data-project-id="' + project.id + '">' +
      '<div><h3>' + escapeHtml(project.name) + '</h3><p>' +
      sourceLabels[project.source_type] + ' · ' + escapeHtml(project.description || "暂无简介") +
      '</p></div><div class="project-meta">' + project.target_episodes +
      ' 集 · ' + project.episode_duration_seconds + ' 秒 · ' + project.status + '</div></article>';
  }).join("");
  projectList.querySelectorAll("[data-project-id]").forEach((item) => {
    item.addEventListener("click", () => selectProject(item.dataset.projectId));
  });
}

async function selectProject(projectId) {
  const response = await fetch("/api/projects/" + projectId);
  if (!response.ok) throw new Error("无法加载项目");
  selectedProject = await response.json();
  document.querySelector("#selected-project-name").textContent = selectedProject.name;
  document.querySelector("#selected-project-meta").textContent =
    selectedProject.target_episodes + " 集 · " + selectedProject.episode_duration_seconds + " 秒";
  workspace.classList.remove("hidden");
  editor.classList.add("hidden");
  await loadSource();
  await loadPlanning();
  await loadProjects();
  workspace.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function loadSource() {
  const response = await fetch("/api/projects/" + selectedProject.id + "/source");
  if (!response.ok) throw new Error("无法加载原始内容");
  const source = await response.json();
  document.querySelector("#source-title").value = source ? source.title : "";
  document.querySelector("#source-content").value = source ? source.content : "";
  document.querySelector("#source-message").textContent = source
    ? "当前版本 v" + source.version + "，保存新内容会生成新版本。"
    : "尚未导入原始内容。";
}

async function loadPlanning() {
  const response = await fetch("/api/projects/" + selectedProject.id + "/planning");
  if (!response.ok) throw new Error("无法加载整剧规划");
  const plans = await response.json();
  if (!plans.length) {
    planning.classList.add("hidden");
    return;
  }
  planning.classList.remove("hidden");
  document.querySelector("#plan-meta").textContent =
    "版本 v" + plans[0].plan_version + " · " + plans.length + " 集";
  document.querySelector("#plan-list").innerHTML = plans.map((plan) =>
    '<button class="plan-item" data-episode="' + plan.episode_number + '">' +
    '<span class="episode-number">第' + plan.episode_number + '集</span>' +
    '<span class="plan-title">' + escapeHtml(plan.title) + '</span>' +
    '<span class="plan-status">' + statusLabels[plan.status] + '</span>' +
    '</button>'
  ).join("");
  document.querySelectorAll("[data-episode]").forEach((item) => {
    item.addEventListener("click", () => openEpisode(Number(item.dataset.episode)));
  });
}

async function openEpisode(episodeNumber) {
  const response = await fetch("/api/projects/" + selectedProject.id + "/planning");
  const plans = await response.json();
  selectedEpisode = plans.find((plan) => plan.episode_number === episodeNumber);
  if (!selectedEpisode) return;
  document.querySelector("#editor-title").textContent = "编辑第" + episodeNumber + "集规划";
  document.querySelector("#episode-title").value = selectedEpisode.title;
  document.querySelector("#episode-status").value = selectedEpisode.status;
  document.querySelector("#episode-logline").value = selectedEpisode.logline;
  document.querySelector("#episode-summary").value = selectedEpisode.plot_summary;
  document.querySelector("#episode-conflict").value = selectedEpisode.key_conflict;
  document.querySelector("#episode-hook").value = selectedEpisode.ending_hook;
  document.querySelector("#episode-message").textContent = "";
  editor.classList.remove("hidden");
  editor.scrollIntoView({ behavior: "smooth", block: "start" });
}

document.querySelector("#source-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  document.querySelector("#source-title").value ||= file.name.replace(/\.[^.]+$/, "");
  document.querySelector("#source-content").value = await file.text();
});

document.querySelector("#save-source").addEventListener("click", async () => {
  if (!selectedProject) return;
  const message = document.querySelector("#source-message");
  try {
    const response = await fetch("/api/projects/" + selectedProject.id + "/source", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: document.querySelector("#source-title").value,
        content: document.querySelector("#source-content").value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "保存失败");
    message.style.color = "#217c48";
    message.textContent = "原始内容已保存，当前版本 v" + data.version;
    await loadProjects();
  } catch (error) {
    message.style.color = "#b03a4b";
    message.textContent = error.message;
  }
});

document.querySelector("#generate-plan").addEventListener("click", async () => {
  if (!selectedProject) return;
  const message = document.querySelector("#source-message");
  try {
    const response = await fetch("/api/projects/" + selectedProject.id + "/planning/generate", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "生成规划失败");
    message.style.color = "#217c48";
    message.textContent = "已生成整剧规划 v" + data.plan_version + "，共 " + data.episode_count + " 集";
    await loadPlanning();
    await loadProjects();
  } catch (error) {
    message.style.color = "#b03a4b";
    message.textContent = error.message;
  }
});

document.querySelector("#episode-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedProject || !selectedEpisode) return;
  const message = document.querySelector("#episode-message");
  try {
    const response = await fetch("/api/projects/" + selectedProject.id + "/planning/" + selectedEpisode.episode_number, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: document.querySelector("#episode-title").value,
        status: document.querySelector("#episode-status").value,
        logline: document.querySelector("#episode-logline").value,
        plot_summary: document.querySelector("#episode-summary").value,
        key_conflict: document.querySelector("#episode-conflict").value,
        ending_hook: document.querySelector("#episode-hook").value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "保存失败");
    selectedEpisode = data;
    message.style.color = "#217c48";
    message.textContent = "本集规划已保存";
    await loadPlanning();
  } catch (error) {
    message.style.color = "#b03a4b";
    message.textContent = error.message;
  }
});

document.querySelector("#close-editor").addEventListener("click", () => editor.classList.add("hidden"));

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = document.querySelector("#form-message");
  try {
    const response = await fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name: document.querySelector("#name").value,
        source_type: document.querySelector("#source_type").value,
        description: document.querySelector("#description").value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "创建失败");
    form.reset();
    message.style.color = "#217c48";
    message.textContent = "项目创建成功";
    await loadProjects();
    await selectProject(data.id);
  } catch (error) {
    message.style.color = "#b03a4b";
    message.textContent = error.message;
  }
});

document.querySelector("#refresh").addEventListener("click", () => loadProjects());
function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  }[character]));
}

checkHealth();
loadProjects().catch((error) => {
  projectList.innerHTML = '<p class="message">' + escapeHtml(error.message) + '</p>';
});



const parsedAssets = document.querySelector("#parsed-assets");
const parseMessage = document.querySelector("#source-message");

async function loadParsedAssets() {
  if (!selectedProject) return;
  const [charactersResponse, locationsResponse, scriptsResponse] = await Promise.all([
    fetch("/api/projects/" + selectedProject.id + "/characters"),
    fetch("/api/projects/" + selectedProject.id + "/locations"),
    fetch("/api/projects/" + selectedProject.id + "/scripts"),
  ]);
  if (!charactersResponse.ok || !locationsResponse.ok || !scriptsResponse.ok) {
    throw new Error("无法加载解析结果");
  }
  const characters = await charactersResponse.json();
  const locations = await locationsResponse.json();
  const scripts = await scriptsResponse.json();
  if (!characters.length && !locations.length && !scripts.length) {
    parsedAssets.classList.add("hidden");
    return;
  }
  parsedAssets.classList.remove("hidden");
  document.querySelector("#parse-meta").textContent =
    characters.length + " 个角色 · " + locations.length + " 个场景 · " +
    scripts.length + " 集剧本草稿";
  document.querySelector("#characters").innerHTML = characters.length
    ? characters.map((item) => '<div class="asset-item"><strong>' +
      escapeHtml(item.name) + '</strong><span>' +
      escapeHtml(item.description || "待补充设定") + '</span></div>').join("")
    : '<p class="muted">暂无角色</p>';
  document.querySelector("#locations").innerHTML = locations.length
    ? locations.map((item) => '<div class="asset-item"><strong>' +
      escapeHtml(item.name) + '</strong><span>' +
      escapeHtml(item.time_of_day || item.description || "待补充设定") + '</span></div>').join("")
    : '<p class="muted">暂无场景</p>';
  document.querySelector("#scripts").innerHTML = scripts.length
    ? scripts.map((item) => '<div class="script-item"><span>第' +
      item.episode_number + '集</span><strong>' + escapeHtml(item.title) +
      '</strong><p>' + escapeHtml(item.synopsis || "待补充单集剧本") + '</p></div>').join("")
    : '<p class="muted">请先生成整剧规划</p>';
}

document.querySelector("#parse-source").addEventListener("click", async () => {
  if (!selectedProject) return;
  try {
    const response = await fetch("/api/projects/" + selectedProject.id + "/parse", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "解析失败");
    parseMessage.style.color = "#217c48";
    parseMessage.textContent = "解析完成：识别 " + data.character_count + " 个角色、" +
      data.location_count + " 个场景，生成 " + data.script_count + " 集剧本草稿";
    await loadParsedAssets();
    await loadProjects();
  } catch (error) {
    parseMessage.style.color = "#b03a4b";
    parseMessage.textContent = error.message;
  }
});

