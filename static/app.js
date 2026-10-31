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



let editableCharacters = [];
let editableLocations = [];
let editableScripts = [];

async function loadEditableAssets() {
  if (!selectedProject) return;
  const base = "/api/projects/" + selectedProject.id;
  const [charactersResponse, locationsResponse, scriptsResponse] = await Promise.all([
    fetch(base + "/characters"), fetch(base + "/locations"), fetch(base + "/scripts"),
  ]);
  editableCharacters = await charactersResponse.json();
  editableLocations = await locationsResponse.json();
  editableScripts = await scriptsResponse.json();
  if (!editableCharacters.length && !editableLocations.length && !editableScripts.length) return;
  document.querySelector("#asset-editor").classList.remove("hidden");
  document.querySelector("#script-editor").classList.toggle("hidden", !editableScripts.length);
  const characterSelect = document.querySelector("#character-select");
  const locationSelect = document.querySelector("#location-select");
  const scriptSelect = document.querySelector("#script-select");
  characterSelect.innerHTML = editableCharacters.map((item) =>
    '<option value="' + item.id + '">' + escapeHtml(item.name) + '</option>').join("");
  locationSelect.innerHTML = editableLocations.map((item) =>
    '<option value="' + item.id + '">' + escapeHtml(item.name) + '</option>').join("");
  scriptSelect.innerHTML = editableScripts.map((item) =>
    '<option value="' + item.episode_number + '">第' + item.episode_number + '集 · ' +
    escapeHtml(item.title) + '</option>').join("");
  fillCharacterForm();
  fillLocationForm();
  fillScriptForm();
  await loadSceneEditor();
}

function fillCharacterForm() {
  const item = editableCharacters.find((entry) =>
    entry.id === document.querySelector("#character-select").value);
  if (!item) return;
  document.querySelector("#character-name").value = item.name;
  document.querySelector("#character-role").value = item.role_type;
  document.querySelector("#character-voice").value = item.voice_name;
  document.querySelector("#character-description").value = item.description;
  document.querySelector("#character-image").value = item.reference_image_path;
}

function fillLocationForm() {
  const item = editableLocations.find((entry) =>
    entry.id === document.querySelector("#location-select").value);
  if (!item) return;
  document.querySelector("#location-name").value = item.name;
  document.querySelector("#location-time").value = item.time_of_day;
  document.querySelector("#location-description").value = item.description;
  document.querySelector("#location-image").value = item.reference_image_path;
}

function fillScriptForm() {
  const item = editableScripts.find((entry) =>
    String(entry.episode_number) === document.querySelector("#script-select").value);
  if (!item) return;
  document.querySelector("#script-title").value = item.title;
  document.querySelector("#script-status").value = item.status;
  document.querySelector("#script-synopsis").value = item.synopsis;
  document.querySelector("#script-dialogue").value = item.dialogue_text;
}

async function loadSceneEditor() {
  const episode = document.querySelector("#script-select").value;
  if (!episode || !selectedProject) return;
  const response = await fetch("/api/projects/" + selectedProject.id + "/scripts/" + episode + "/scenes");
  const scenes = await response.json();
  document.querySelector("#scene-editor").innerHTML = scenes.map((scene) =>
    '<div class="scene-card"><h3>第' + scene.scene_number + '场</h3>' +
    '<div class="scene-grid"><label>地点<input data-scene-field="location_name" value="' +
    escapeAttr(scene.location_name) + '"></label><label>时间<input data-scene-field="time_of_day" value="' +
    escapeAttr(scene.time_of_day) + '"></label><label class="wide">出场人物<input data-scene-field="character_names" value="' +
    escapeAttr(scene.character_names.join("、")) + '"></label><label class="wide">动作<textarea data-scene-field="action_text">' +
    escapeHtml(scene.action_text) + '</textarea></label><label class="wide">对白<textarea data-scene-field="dialogue_text">' +
    escapeHtml(scene.dialogue_text) + '</textarea></label></div><button class="secondary save-scene" data-scene="' +
    scene.scene_number + '">保存本场</button></div>'
  ).join("");
  document.querySelectorAll(".save-scene").forEach((button) => {
    button.addEventListener("click", () => saveScene(Number(button.dataset.scene)));
  });
}

async function saveScene(sceneNumber) {
  const episode = document.querySelector("#script-select").value;
  const card = [...document.querySelectorAll(".scene-card")].find((item) =>
    item.querySelector(".save-scene").dataset.scene === String(sceneNumber));
  const value = (field) => card.querySelector('[data-scene-field="' + field + '"]').value;
  const response = await fetch("/api/projects/" + selectedProject.id + "/scripts/" + episode + "/scenes/" + sceneNumber, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      location_name: value("location_name"),
      time_of_day: value("time_of_day"),
      character_names: value("character_names").split(/[、,，]/).map((item) => item.trim()).filter(Boolean),
      action_text: value("action_text"),
      dialogue_text: value("dialogue_text"),
    }),
  });
  const data = await response.json();
  const message = document.querySelector("#script-message");
  message.style.color = response.ok ? "#217c48" : "#b03a4b";
  message.textContent = response.ok ? "场景已保存" : (data.detail || "保存场景失败");
}

document.querySelector("#parse-source").addEventListener("click", () => {
  setTimeout(() => loadEditableAssets().catch(() => {}), 250);
});
document.querySelector("#character-select").addEventListener("change", fillCharacterForm);
document.querySelector("#location-select").addEventListener("change", fillLocationForm);
document.querySelector("#script-select").addEventListener("change", () => {
  fillScriptForm();
  loadSceneEditor().catch(() => {});
});

document.querySelector("#character-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.querySelector("#character-select").value;
  const response = await fetch("/api/projects/" + selectedProject.id + "/characters/" + id, {
    method: "PATCH", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      name: document.querySelector("#character-name").value,
      role_type: document.querySelector("#character-role").value,
      voice_name: document.querySelector("#character-voice").value,
      description: document.querySelector("#character-description").value,
      reference_image_path: document.querySelector("#character-image").value,
    }),
  });
  const message = document.querySelector("#asset-message");
  message.style.color = response.ok ? "#217c48" : "#b03a4b";
  message.textContent = response.ok ? "角色设定已保存" : "角色保存失败";
  if (response.ok) await loadEditableAssets();
});

document.querySelector("#location-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const id = document.querySelector("#location-select").value;
  const response = await fetch("/api/projects/" + selectedProject.id + "/locations/" + id, {
    method: "PATCH", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      name: document.querySelector("#location-name").value,
      time_of_day: document.querySelector("#location-time").value,
      description: document.querySelector("#location-description").value,
      reference_image_path: document.querySelector("#location-image").value,
    }),
  });
  const message = document.querySelector("#asset-message");
  message.style.color = response.ok ? "#217c48" : "#b03a4b";
  message.textContent = response.ok ? "场景设定已保存" : "场景保存失败";
  if (response.ok) await loadEditableAssets();
});

document.querySelector("#script-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const episode = document.querySelector("#script-select").value;
  const response = await fetch("/api/projects/" + selectedProject.id + "/scripts/" + episode, {
    method: "PATCH", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      title: document.querySelector("#script-title").value,
      status: document.querySelector("#script-status").value,
      synopsis: document.querySelector("#script-synopsis").value,
      dialogue_text: document.querySelector("#script-dialogue").value,
    }),
  });
  const data = await response.json();
  const message = document.querySelector("#script-message");
  message.style.color = response.ok ? "#217c48" : "#b03a4b";
  message.textContent = response.ok ? "单集剧本已保存" : (data.detail || "保存失败");
  if (response.ok) await loadEditableAssets();
});

function escapeAttr(value) {
  return escapeHtml(value);
}



async function loadStoryboard() {
  if (!selectedProject) return;
  const episode = document.querySelector("#script-select").value;
  if (!episode) return;
  const response = await fetch("/api/projects/" + selectedProject.id + "/scripts/" + episode + "/storyboard");
  if (!response.ok) throw new Error("无法加载分镜");
  const shots = await response.json();
  const storyboardEditor = document.querySelector("#storyboard-editor");
  if (!shots.length) {
    storyboardEditor.classList.add("hidden");
    return;
  }
  storyboardEditor.classList.remove("hidden");
  document.querySelector("#storyboard-meta").textContent =
    shots.length + " 个镜头 · " + shots.reduce((sum, shot) => sum + shot.duration_seconds, 0) + " 秒";
  document.querySelector("#shot-list").innerHTML = shots.map((shot) =>
    '<article class="shot-card" data-shot="' + shot.shot_number + '">' +
    '<h4>镜头 ' + shot.shot_number + ' <span>第' + shot.scene_number + '场</span></h4>' +
    '<div class="scene-grid"><label>景别<input data-shot-field="shot_type" value="' + escapeAttr(shot.shot_type) + '"></label>' +
    '<label>机位 / 运镜<input data-shot-field="camera" value="' + escapeAttr(shot.camera) + '"></label>' +
    '<label>时长（秒）<input type="number" min="1" max="60" data-shot-field="duration_seconds" value="' + shot.duration_seconds + '"></label>' +
    '<label>地点<input data-shot-field="location_name" value="' + escapeAttr(shot.location_name) + '"></label>' +
    '<label class="wide">画面描述<textarea data-shot-field="visual_description">' + escapeHtml(shot.visual_description) + '</textarea></label>' +
    '<label class="wide">动作<textarea data-shot-field="action_text">' + escapeHtml(shot.action_text) + '</textarea></label>' +
    '<label class="wide">对白<textarea data-shot-field="dialogue_text">' + escapeHtml(shot.dialogue_text) + '</textarea></label>' +
    '</div><button class="secondary save-shot" data-shot="' + shot.shot_number + '">保存镜头</button></article>'
  ).join("");
  document.querySelectorAll(".save-shot").forEach((button) => {
    button.addEventListener("click", () => saveShot(Number(button.dataset.shot)));
  });
}

async function saveShot(shotNumber) {
  const episode = document.querySelector("#script-select").value;
  const card = document.querySelector('.shot-card[data-shot="' + shotNumber + '"]');
  const value = (field) => card.querySelector('[data-shot-field="' + field + '"]').value;
  const response = await fetch("/api/projects/" + selectedProject.id + "/scripts/" + episode + "/storyboard/" + shotNumber, {
    method: "PATCH",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      shot_type: value("shot_type"),
      camera: value("camera"),
      duration_seconds: Number(value("duration_seconds")),
      visual_description: value("visual_description"),
      action_text: value("action_text"),
      dialogue_text: value("dialogue_text"),
      character_names: [],
      location_name: value("location_name"),
      status: "draft",
    }),
  });
  const data = await response.json();
  const message = document.querySelector("#script-message");
  message.style.color = response.ok ? "#217c48" : "#b03a4b";
  message.textContent = response.ok ? "镜头已保存" : (data.detail || "保存镜头失败");
  if (response.ok) await loadStoryboard();
}

document.querySelector("#script-select").addEventListener("change", () => {
  loadStoryboard().catch(() => {});
});
document.querySelector("#generate-storyboard").addEventListener("click", async () => {
  if (!selectedProject) return;
  const episode = document.querySelector("#script-select").value;
  const message = document.querySelector("#script-message");
  try {
    const response = await fetch("/api/projects/" + selectedProject.id + "/scripts/" + episode + "/storyboard/generate", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "分镜生成失败");
    message.style.color = "#217c48";
    message.textContent = "已生成 " + data.shot_count + " 个镜头，共 " + data.total_duration_seconds + " 秒";
    await loadStoryboard();
  } catch (error) {
    message.style.color = "#b03a4b";
    message.textContent = error.message;
  }
});

