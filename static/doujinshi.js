const token = localStorage.getItem("token");
let rm_group = false;
let rm_group_progress = [0, 1];

async function getServerInfo() {
    const res = await fetch("/", { headers: { Authorization: "Bearer " + token } });
    return JSON.parse(await res.text());
}

async function getGroups() {
    const res = await fetch("/group", { headers: { Authorization: "Bearer " + token } });
    return JSON.parse(await res.text()).data;
}

let count = 1;
async function getProgress(url) {
    if (rm_group) {
        return rm_group_progress;
    }
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

async function setBatch(type, value, datas) {
    if (type == "group_rm") {
        rm_group = true;
        rm_group_progress[0] = 0;
        rm_group_progress[1] = datas.length;
        for (let data of datas) {
            await fetch(`/group/${value}/${data}`, {
                method: "DELETE",
                headers: { Authorization: "Bearer " + token}});
            await new Promise((resolve) => setTimeout(resolve, 500));
            rm_group_progress[0] += 1;
        }
        return;
    }
    else {
        rm_group = false;
    }
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
    const res = await fetch("/group", { headers: { Authorization: "Bearer " + token } });
    let result = JSON.parse(await res.text());
    return result.data;
}

async function updateGroup(id, name) {
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
    fetch("/settings", {
        method: "POST",
        headers: { Authorization: "Bearer " + token, "Content-Type": "application/json" },
        body: JSON.stringify({
            proxy_webpage: proxy_img,
            max_num_perpage: num
        })
    });
}