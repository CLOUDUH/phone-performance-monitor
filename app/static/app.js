(function () {
  "use strict";

  var stage = document.getElementById("monitor-stage");
  var dashboard = document.getElementById("dashboard");
  var lastData = null;
  var lastHistoryTime = 0;
  var history = { router: [], devices: [] };
  var historyLimit = 60;
  var clockEpoch = Date.now();
  var clockReceivedAt = Date.now();
  var slots = [
    { label: "UBCLOUD", detail: "Intel 14700K + NVIDIA 4070Super", aliases: ["ubcloud", "ub", "ubuntu"], third: "gpu", thirdLabel: "GPU" },
    { label: "MACCLOUD", detail: "Apple MacBook Pro M1 Pro 2021", aliases: ["maccloud", "mac", "macbook"], third: "temperature", thirdLabel: "温度" },
    { label: "SYNCLOUD", detail: "Synology DS423+", aliases: ["syncloud", "nas", "synology"], third: "temperature", thirdLabel: "温度" },
    { label: "PVECLOUD", detail: "Beelink EQ13 mini Intel N95", aliases: ["pvecloud", "pve", "proxmox"], third: "temperature", thirdLabel: "温度" }
  ];

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[character];
    });
  }

  function clamp(value) { return Math.max(0, Math.min(100, Number(value) || 0)); }
  function percent(value) { return value == null ? "--" : Math.round(Number(value)) + "%"; }
  function temperature(value) { return value == null ? "--" : Math.round(Number(value)) + "°C"; }
  function pad(value) { return value < 10 ? "0" + value : String(value); }

  function formatRate(value) {
    value = Number(value) || 0;
    if (value >= 1000000000) return (value / 1000000000).toFixed(2) + " Gbps";
    if (value >= 1000000) return (value / 1000000).toFixed(1) + " Mbps";
    if (value >= 1000) return (value / 1000).toFixed(0) + " Kbps";
    return Math.round(value) + " bps";
  }

  function fitStage() {
    var scale = Math.min(window.innerWidth / 1080, window.innerHeight / 1920);
    var transform = "translate(-50%, -50%) scale(" + scale + ")";
    stage.style.webkitTransform = transform;
    stage.style.transform = transform;
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

  function metricColor(value, kind) {
    if (value == null) return "#5d5d5d";
    value = Number(value) || 0;
    if (kind === "temperature") {
      if (value < 55) return "#65d89b";
      if (value < 70) return "#f0b75a";
      return "#ee6f78";
    }
    if (value < 60) return "#65d89b";
    if (value < 80) return "#f0b75a";
    return "#ee6f78";
  }

  function metric(label, value, rawValue, kind) {
    var width = rawValue == null ? 0 : clamp(rawValue);
    var color = metricColor(rawValue, kind);
    return '<div class="metric-line"><div class="metric-caption"><span>' + escapeHtml(label) + '</span>' +
      '<strong>' + escapeHtml(value) + '</strong></div><div class="metric-track">' +
      '<i class="metric-fill" style="width:' + width + '%;background-color:' + color + '"></i></div></div>';
  }

  function loadAverage(system) {
    if (!system || !system.load || system.load.length === 0 || system.load[0] == null) return null;
    var value = Number(system.load[0]);
    return isFinite(value) ? value : null;
  }

  function loadPercent(system, value) {
    if (value == null) return null;
    var threads = Number(system && system.threads) || 0;
    return threads > 0 ? value / threads * 100 : value * 10;
  }

  function deviceCard(slot, system, position) {
    var online = system && system.status === "up";
    var thirdValue = system ? system[slot.third] : null;
    var thirdText = slot.third === "temperature" ? temperature(thirdValue) : percent(thirdValue);
    var thirdRing = slot.third === "temperature" ? clamp(thirdValue) : thirdValue;
    var load = loadAverage(system);
    return '<article class="device-panel device-' + position + '">' +
      '<header class="device-header"><div><div class="device-label">' + escapeHtml(slot.label) + '</div>' +
      '<div class="device-detail">' + escapeHtml(slot.detail) + '</div></div>' +
      '<div class="device-state ' + (online ? "online" : "offline") + '"><i></i>' + (online ? "在线" : "离线") + '</div></header>' +
      '<div class="metric-list">' +
        metric("CPU", percent(system && system.cpu), system && system.cpu, "percent") +
        metric("内存", percent(system && system.memory), system && system.memory, "percent") +
        metric(slot.thirdLabel, thirdText, thirdRing, slot.third) +
        metric("系统负载", load == null ? "--" : load.toFixed(2), loadPercent(system, load), "percent") +
      '</div></article>';
  }

  function currentClock() {
    var beijing = new Date(clockEpoch + (Date.now() - clockReceivedAt) + 8 * 3600000);
    return pad(beijing.getUTCHours()) + ":" + pad(beijing.getUTCMinutes()) + ":" + pad(beijing.getUTCSeconds());
  }

  function weatherLine(weather) {
    if (!weather || (weather.status !== "up" && weather.status !== "stale")) return "天气数据暂不可用";
    return Math.round(Number(weather.minimum)) + "–" + Math.round(Number(weather.maximum)) + "°C  " +
      escapeHtml(weather.condition || "天气未知") + "  降雨" + Math.round(Number(weather.precipitation_probability) || 0) + "%";
  }

  function timePanel(data) {
    var calendar = data.calendar || {};
    var dateLine = calendar.date ? calendar.date + "  " + calendar.weekday + "  " + calendar.lunar : "正在获取日期";
    return '<header class="time-panel"><strong id="beijing-clock">' + currentClock() + '</strong>' +
      '<span id="beijing-date">' + escapeHtml(dateLine) + '</span>' +
      '<span id="beijing-weather">' + weatherLine(data.weather) + '</span></header>';
  }

  function tickClock() {
    var clock = document.getElementById("beijing-clock");
    if (clock) clock.textContent = currentClock();
  }

  function sumRates(systems) {
    return systems.reduce(function (total, system) {
      total.down += Number(system.network_down_bps) || 0;
      total.up += Number(system.network_up_bps) || 0;
      return total;
    }, { down: 0, up: 0 });
  }

  function rememberNetwork(data, systems) {
    var timestamp = Number(data.server_time) || Date.now() / 1000;
    if (timestamp === lastHistoryTime) return;
    lastHistoryTime = timestamp;
    var wan = data.wan || {};
    var devices = sumRates(systems);
    history.router.push({ down: Number(wan.download_bps) || 0, up: Number(wan.upload_bps) || 0 });
    history.devices.push(devices);
    if (history.router.length > historyLimit) history.router.shift();
    if (history.devices.length > historyLimit) history.devices.shift();
  }

  function chartCard(id, title, subtitle, rates) {
    return '<section class="chart-card"><div class="chart-title"><strong>' + escapeHtml(title) + '</strong><span>' + escapeHtml(subtitle) + '</span></div>' +
      '<div class="chart-values"><div><span>↓ 下载</span><strong class="download-value">' + formatRate(rates.down) + '</strong></div>' +
      '<div><span>↑ 上传</span><strong class="upload-value">' + formatRate(rates.up) + '</strong></div></div>' +
      '<canvas id="' + id + '" class="throughput-chart" width="424" height="350"></canvas>' +
      '<div class="chart-legend"><span class="download-legend"><i></i>下载</span><span class="upload-legend"><i></i>上传</span><em>最近 60 个采样点</em></div></section>';
  }

  function networkCharts(data, systems, connectionState) {
    var wan = data.wan || {};
    var deviceRates = sumRates(systems);
    var routerRates = { down: Number(wan.download_bps) || 0, up: Number(wan.upload_bps) || 0 };
    return '<section class="network-panel"><div class="network-heading"><div><strong>实时网络吞吐</strong><span>下载与上传速度趋势</span></div>' +
      '<div class="stream-state ' + connectionState + '"><i></i><span>' + (connectionState === "live" ? "数据流已连接" : "正在连接") + '</span></div></div>' +
      '<div class="network-charts">' +
        chartCard("router-chart", "路由器", "爱快 WAN 总吞吐", routerRates) +
        chartCard("devices-chart", "全部设备", "Beszel 设备合计吞吐", deviceRates) +
      '</div></section>';
  }

  function niceMaximum(value) {
    if (!value || value < 1000) return 1000;
    var power = Math.pow(10, Math.floor(Math.log(value) / Math.LN10));
    var scaled = value / power;
    var nice = scaled <= 1 ? 1 : scaled <= 2 ? 2 : scaled <= 5 ? 5 : 10;
    return nice * power;
  }

  function drawChart(canvas, points) {
    if (!canvas || !canvas.getContext) return;
    var context = canvas.getContext("2d");
    var width = canvas.width;
    var height = canvas.height;
    var left = 70;
    var right = 18;
    var top = 26;
    var bottom = 42;
    var plotWidth = width - left - right;
    var plotHeight = height - top - bottom;
    var maximum = niceMaximum(points.reduce(function (highest, point) {
      return Math.max(highest, point.down, point.up);
    }, 0));

    context.clearRect(0, 0, width, height);
    context.font = "17px sans-serif";
    context.textAlign = "right";
    context.textBaseline = "middle";
    for (var line = 0; line <= 4; line += 1) {
      var y = top + plotHeight * line / 4;
      context.beginPath();
      context.strokeStyle = "#3b3b3b";
      context.lineWidth = 1;
      context.moveTo(left, y);
      context.lineTo(width - right, y);
      context.stroke();
      context.fillStyle = "#888";
      context.fillText(formatRate(maximum * (4 - line) / 4), left - 10, y);
    }

    function series(field, color) {
      if (!points.length) return;
      context.beginPath();
      context.strokeStyle = color;
      context.lineWidth = 4;
      context.lineJoin = "round";
      context.lineCap = "round";
      points.forEach(function (point, index) {
        var x = points.length === 1 ? left : left + plotWidth * index / (points.length - 1);
        var y = top + plotHeight * (1 - Math.min(Number(point[field]) || 0, maximum) / maximum);
        if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
      });
      if (points.length === 1) context.lineTo(width - right, top + plotHeight * (1 - Math.min(Number(points[0][field]) || 0, maximum) / maximum));
      context.stroke();
    }

    series("down", "#6ba8ff");
    series("up", "#65d89b");
  }

  function render(data, connectionState) {
    lastData = data;
    if (data.server_time) {
      clockEpoch = Number(data.server_time) * 1000;
      clockReceivedAt = Date.now();
    }
    var systems = (data.beszel && data.beszel.systems) || [];
    rememberNetwork(data, systems);
    var used = {};
    var matched = slots.map(function (slot) {
      var system = findSystem(slot, systems, used);
      if (system) used[system.id] = true;
      return system || null;
    });
    dashboard.innerHTML = timePanel(data) + deviceCard(slots[0], matched[0], 1) + deviceCard(slots[1], matched[1], 2) +
      deviceCard(slots[2], matched[2], 3) + deviceCard(slots[3], matched[3], 4) +
      networkCharts(data, systems, connectionState || "waiting");
    drawChart(document.getElementById("router-chart"), history.router);
    drawChart(document.getElementById("devices-chart"), history.devices);
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
  window.setInterval(tickClock, 250);
  window.addEventListener("resize", fitStage);
})();
