const token = localStorage.getItem("token");
let rm_group = false;
let rm_group_progress = [0, 1];

async function getServerInfo() {
    const res = await fetch("/", { headers: { Authorization: "Bearer " + token } });
    return JSON.parse(await res.text());
}

async function getImg(url) {
    const res = await fetch(url, { headers: { Authorization: "Bearer " + token } });
    const blob = await res.blob();
    return blob;
}

async function getGroups() {
    const res = await fetch("/group", { headers: { Authorization: "Bearer " + token } });
    return JSON.parse(await res.text()).data;
}

async function getTags(type) {
    const res = await fetch(`/tags/${type}`, { headers: { Authorization: "Bearer " + token } });
    return JSON.parse(await res.text()).data;
}

async function getProgress(url) {
    if (rm_group) {
        return [(rm_group_progress[0] == rm_group_progress[1]), `removing groups ${rm_group_progress[0]}/${rm_group_progress[1]}`];
    }
    const res = await fetch(url, { headers: { Authorization: "Bearer " + token } });
    let result = JSON.parse(await res.text());
    let finished = false;
    if ((result.msg == "none") || (result.msg == "finished") || (result.msg == "scanning has not started")) {
        finished = true;
    }
    return [finished, result.msg];
}

function parseDatas(datas) {
    const results = [];
    for (let data of datas) {
        let result = {
            id: data.id,
            title: data.title,
            hascover: data.cover != "/doujinshi/nothumb/thumbnail",
            tags: data.tags,
            groups: data.groups,
            source: data.source
        };
        if ("translated_tags" in data) {
            result["translated_tags"] = data.translated_tags;
        }
        results.push(result);
    }
    return results;
}

async function getDatas(query, group, source, page, reverse) {
    if (reverse) {
        page = -page;
    }
    const url = `/search?query=${query}&group=${group}&source_name=${source}&page=${page}`;
    const res = await fetch(url, { headers: { Authorization: "Bearer " + token } });
    return parseDatas(JSON.parse(await res.text()).data.doujinshis)
}

async function getRandomDatas(num) {
    const url = `/doujinshi/random?num=${num}`;
    const res = await fetch(url, { headers: { Authorization: "Bearer " + token } });
    return parseDatas(JSON.parse(await res.text()).data.doujinshis)
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

async function getPages(id) {
    const res = await fetch(`/doujinshi/${id}/pages`, { headers: { Authorization: "Bearer " + token } });
    let result = JSON.parse(await res.text());
    if ("urls" in result.data) {
        const urls = [];
        for (let i = 0; i < result.data.urls.length; i++) {
            urls.push(`/doujinshi/${id}/page/${i}`);
        }
        return urls;
    }
    if (result.data[0].search("/pageinfo/") != -1) {
        const urls = [];
        for (let i = 0; i < result.data.length; i++) {
            urls.push(`/doujinshi/${id}/page/${i}`);
        }
        return urls;
    }
    return result.data;
}