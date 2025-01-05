async function getServerInfo() {
    const token = sessionStorage.getItem("token");
    const res = await fetch("/", { headers: { Authorization: "Bearer " + token } });
    return JSON.parse(await res.text());
}

async function getGroups() {
    const token = sessionStorage.getItem("token");
    const res = await fetch("/group", { headers: { Authorization: "Bearer " + token } });
    return JSON.parse(await res.text()).data;
}

let count = 1;
async function getProgress(url) {
    const token = sessionStorage.getItem("token");
    const res = await fetch(url, { headers: { Authorization: "Bearer " + token } });
    let result = JSON.parse(await res.text());
    if (url.search("scan") != -1) {
        return [result.msg];
    }
    if ((result.msg == "none") || (result.msg == "finished")) {
        return [count, count];
    }
    const result_strs = result.msg.split("/");
    count = parseInt(result_strs[1]);
    return [parseInt(result_strs[0].split(" ").slice(-1)), count];
}

async function getDatas(query, group, source, page, reverse) {
    const token = sessionStorage.getItem("token");
    if (reverse) {
        page = -page;
    }
    const url = `/search?query=${query}&group=${group}&source_name=${source}&page=${page}`;
    const res = await fetch(url, { headers: { Authorization: "Bearer " + token } });
    const datas = [];
    for (let data of JSON.parse(await res.text()).data) {
        datas.push({
            id: data.id,
            title: data.title,
            hascover: data.cover != "/doujinshi/nothumb/thumbnail",
            tags: data.tags,
            groups: data.groups,
            source: data.source
        })
    }
    return datas;
}

function setBatch(type, value, datas) {
    const token = sessionStorage.getItem("token");
    fetch("/batch", {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({
            operation: type,
            name: value,
            target: datas,
            replace: false
        })
    });
}

async function updateMetadata(id, title, tags) {
    const token = sessionStorage.getItem("token");
    const res = await fetch(`/doujinshi/${id}/metadata`, {
        method: "PUT",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({
            title: title,
            tag: tags
        })
    });
    let result = JSON.parse(await res.text());
    if (res.ok && (result.msg.search("success") != -1)) {
        return true;
    }
    return false;
}

async function deleteMetadata(id) {
    const token = sessionStorage.getItem("token");
    const res = await fetch(`/doujinshi/${id}/metadata`, {
        method: "DELETE",
        headers: { Authorization: "Bearer " + token }
    });
    let result = JSON.parse(await res.text());
    if (res.ok && (result.msg.search("success") != -1)) {
        return true;
    }
    return false;
}

async function getGroup() {
    const token = sessionStorage.getItem("token");
    const res = await fetch("/group", { headers: { Authorization: "Bearer " + token } });
    let result = JSON.parse(await res.text());
    return result.data;
}

async function updateGroup(id, name) {
    const token = sessionStorage.getItem("token");
    const res = await fetch("/group/" + id, {
        method: "PUT",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({ name: name })
    });
    let result = JSON.parse(await res.text());
    if (res.ok && (result.msg.search("success") != -1)) {
        return true;
    }
    return false;
}

async function deleteGroup(id) {
    const token = sessionStorage.getItem("token");
    const res = await fetch("/group/" + id, {
        method: "DELETE",
        headers: { Authorization: "Bearer " + token }
    });
    let result = JSON.parse(await res.text());
    if (res.ok && (result.msg.search("success") != -1)) {
        return true;
    }
    return false;
}

function scanSource(source) {
    const token = sessionStorage.getItem("token");
    fetch("/scan", {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({
            start: true,
            source_name: source
        })
    });
}

function addSource(source, datas) {
    const token = sessionStorage.getItem("token");
    fetch("/add", {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({
            source_name: source,
            target: datas,
            replace: false
        })
    });
}

function updateSettings(proxy_img, num) {
    const token = sessionStorage.getItem("token");
    fetch("/settings", {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({
            proxy_webpage: proxy_img,
            max_num_perpage: num
        })
    });
}