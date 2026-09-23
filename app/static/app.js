(function () {
  "use strict";

  var stage = document.getElementById("monitor-stage");
  var dashboard = document.getElementById("dashboard");
  var lastData = null;
  var slots = [
    { label: "UB", aliases: ["ub", "ubuntu"], third: "gpu", thirdLabel: "GPU" },
    { label: "Mac", aliases: ["mac", "macbook"], third: "gpu", thirdLabel: "GPU" },
    { label: "NAS", aliases: ["nas", "synology"], third: "temperature", thirdLabel: "温度" },
    { label: "PVE", aliases: ["pve", "proxmox"], third: "temperature", thirdLabel: "温度" }
  ];

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[character];
    });
  }

  function clamp(value) { return Math.max(0, Math.min(100, Number(value) || 0)); }
  function percent(value) { return value == null ? "--" : Math.round(Number(value)) + "%"; }
  function temperature(value) { return value == null ? "--" : Math.round(Number(value)) + "°C"; }

  function formatRate(value) {
    value = Number(value) || 0;
    if (value >= 1000000000) return (value / 1000000000).toFixed(2) + " Gbps";
    if (value >= 1000000) return (value / 1000000).toFixed(1) + " Mbps";
    if (value >= 1000) return (value / 1000).toFixed(0) + " Kbps";
    return Math.round(value) + " bps";
  }

  function formatUptime(seconds) {
    if (!seconds) return "无运行时间数据";
    var days = Math.floor(seconds / 86400);
    var hours = Math.floor((seconds % 86400) / 3600);
    return "已运行 " + (days ? days + " 天 " : "") + hours + " 小时";
  }

  function fitStage() {
    var scale = Math.min(window.innerWidth / 1920, window.innerHeight / 1080);
    stage.style.transform = "translate(-50%, -50%) scale(" + scale + ")";
  }

  function findSystem(slot, systems, used) {
    var exact = systems.find(function (system) {
      return !used[system.id] && system.name.toLowerCase() === slot.label.toLowerCase();
    });
    if (exact) return exact;
    return systems.find(function (system) {
      var name = system.name.toLowerCase();
      return !used[system.id] && slot.aliases.some(function (alias) { return name.indexOf(alias) !== -1; });
    });
  }

  function metric(label, value, ringValue, accent, unitClass) {
    return '<div class="device-metric">' +
      '<div class="metric-ring" style="--metric-value:' + clamp(ringValue) + ';--metric-accent:' + accent + '">' +
        '<div class="metric-core"><strong class="' + (unitClass || "") + '">' + escapeHtml(value) + '</strong></div>' +
      '</div><span>' + escapeHtml(label) + '</span></div>';
  }

  function deviceCard(slot, system, position) {
    var online = system && system.status === "up";
    var thirdValue = system ? system[slot.third] : null;
    var thirdText = slot.third === "temperature" ? temperature(thirdValue) : percent(thirdValue);
    var thirdRing = slot.third === "temperature" ? clamp(thirdValue) : thirdValue;
    return '<article class="device-panel device-' + position + '">' +
      '<header class="device-header"><div><div class="device-label">' + escapeHtml(slot.label) + '</div>' +
      '<div class="device-detail">' + escapeHtml(system ? system.name + " · " + formatUptime(system.uptime_seconds) : "未匹配到 Beszel 设备") + '</div></div>' +
      '<div class="device-state ' + (online ? "online" : "offline") + '"><i></i>' + (online ? "在线" : "离线") + '</div></header>' +
      '<div class="metric-row">' +
        metric("CPU", percent(system && system.cpu), system && system.cpu, "#36d7ff") +
        metric("内存", percent(system && system.memory), system && system.memory, "#8a7dff") +
        metric(slot.thirdLabel, thirdText, thirdRing, slot.third === "gpu" ? "#ffbd5c" : "#45e0a8", slot.third === "temperature" ? "temperature-value" : "") +
      '</div></article>';
  }

  function networkTable(orderedSystems, connectionState) {
    var rows = orderedSystems.map(function (system) {
      var online = system.status === "up";
      return '<tr><td><div class="table-device"><i class="table-dot ' + (online ? "online" : "") + '"></i>' +
        '<strong>' + escapeHtml(system.displayLabel || system.name) + '</strong><span>' + escapeHtml(system.name) + '</span></div></td>' +
        '<td class="rate download">' + formatRate(system.network_down_bps) + '</td>' +
        '<td class="rate upload">' + formatRate(system.network_up_bps) + '</td></tr>';
    }).join("");
    return '<section class="network-panel"><div class="network-heading"><div><strong>设备网络吞吐</strong><span>Beszel 最近一分钟采样</span></div>' +
      '<div class="stream-state ' + connectionState + '"><i></i><span>' + (connectionState === "live" ? "数据流已连接" : "正在连接") + '</span></div></div>' +
      '<table><thead><tr><th>设备</th><th>↓ 下行速度</th><th>↑ 上行速度</th></tr></thead><tbody>' + rows + '</tbody></table></section>';
  }

  function render(data, connectionState) {
    lastData = data;
    var systems = (data.beszel && data.beszel.systems) || [];
    var used = {};
    var matched = slots.map(function (slot) {
      var system = findSystem(slot, systems, used);
      if (system) used[system.id] = true;
      return system || null;
    });
    var tableSystems = matched.map(function (system, index) {
      var result = system || { id: "missing-" + index, name: "未找到", status: "down", network_down_bps: 0, network_up_bps: 0 };
      return Object.assign({}, result, { displayLabel: slots[index].label });
    });
    systems.forEach(function (system) { if (!used[system.id]) tableSystems.push(system); });
    dashboard.innerHTML = deviceCard(slots[0], matched[0], 1) + deviceCard(slots[1], matched[1], 2) +
      deviceCard(slots[2], matched[2], 3) + deviceCard(slots[3], matched[3], 4) +
      networkTable(tableSystems, connectionState || "waiting");
  }

  function connect() {
    var events = new EventSource("/api/events");
    events.onopen = function () { if (lastData) render(lastData, "live"); };
    events.onmessage = function (event) {
      try { render(JSON.parse(event.data), "live"); } catch (error) { console.error(error); }
    };
    events.onerror = function () { if (lastData) render(lastData, "waiting"); };
  }

  fitStage();
  render({ beszel: { systems: [] } }, "waiting");
  connect();
  window.addEventListener("resize", fitStage);
})();
