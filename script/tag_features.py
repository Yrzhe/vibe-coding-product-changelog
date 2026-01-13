#!/usr/bin/env python3
"""
功能更新打标脚本
支持规则匹配和 LLM 打标两种模式
"""

import json
import re
import time
from pathlib import Path
import requests


def load_config():
    """加载 LLM 配置"""
    config_path = Path(__file__).parent / "prompts" / "llm_config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        configs = json.load(f)
    return configs[0]


def load_tags():
    """加载标签体系"""
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    tags_path = project_root / "info" / "tag.json"
    
    with open(tags_path, "r", encoding="utf-8") as f:
        return json.load(f)


def call_llm(prompt: str, config: dict) -> str:
    """调用 LLM API"""
    headers = {
        "Content-Type": "application/json",
        "x-api-key": config["api_key"],
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": config["model"],
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{config['base_url']}/v1/messages",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return result.get("content", [{}])[0].get("text", "")
    except Exception as e:
        print(f"    LLM 调用失败: {e}")
        return ""


def build_tag_prompt(title: str, description: str, tags_data: list) -> str:
    """构建打标提示词"""
    tags_json = json.dumps(tags_data, ensure_ascii=False, indent=2)
    
    prompt = f"""你是一个竞品分析专家，负责为竞品的功能更新进行分类打标。

## 现有标签体系

{tags_json}

## 待打标的功能

- **标题**: {title}
- **描述**: {description}

## 任务

请从现有标签体系中选择最合适的标签（tag）和子标签（subtag）。

## 输出要求

直接输出 JSON，格式如下：

```json
{{
    "tags": [
        {{
            "name": "标签名称",
            "subtags": [
                {{"name": "子标签1"}},
                {{"name": "子标签2"}}
            ]
        }}
    ]
}}
```

## 规则

1. **优先使用现有标签和子标签**
2. 可以选择多个 tag（通常 1-3 个最相关的）
3. subtag 应该是功能涉及的具体主体（服务名、模型名、具体功能等）
4. 如果现有子标签没有匹配项但功能涉及具体主体，可以添加新的 subtag
5. 如果描述内容太泛或不够具体，subtags 可以为空数组

请直接输出 JSON："""
    
    return prompt


def parse_llm_response(response: str) -> list:
    """解析 LLM 响应"""
    try:
        data = json.loads(response)
        return data.get("tags", [])
    except:
        pass
    
    # 尝试从代码块中提取
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return data.get("tags", [])
        except:
            pass
    
    # 尝试找到 JSON 对象
    json_match = re.search(r'\{[^{}]*"tags"\s*:\s*\[.*?\]\s*\}', response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            return data.get("tags", [])
        except:
            pass
    
    return []


def tag_with_llm(title: str, description: str, config: dict, tags_data: list) -> list:
    """使用 LLM 打标"""
    prompt = build_tag_prompt(title, description, tags_data)
    response = call_llm(prompt, config)
    
    if not response:
        return []
    
    return parse_llm_response(response)


def match_tags_rules(title: str, description: str, tags_data: list) -> list:
    """基于规则匹配标签"""
    matched_tags = []
    text = f"{title} {description}".lower()
    
    # 关键词到标签的映射
    tag_rules = {
        "Integration": [
            r'\bintegrat\w*\b', r'\bconnect\w*\b', r'\bmcp\b', r'\bapi\b',
            r'\bsupabase\b', r'\bstripe\b', r'\bgithub\b', r'\bnotion\b',
            r'\blinear\b', r'\bglean\b', r'\bsnowflake\b', r'\bshopify\b',
            r'\bfigma\b', r'\bslack\b', r'\bsalesforce\b', r'\bzendesk\b',
            r'\btwilio\b', r'\belevenlabs\b', r'\bperplexity\b', r'\bfirecrawl\b',
            r'\bnetlify\b', r'\bvercel\b', r'\bwhatsapp\b', r'\btodoist\b',
            r'\bclickup\b', r'\batlassian\b', r'\bgitlab\b', r'\bbitbucket\b',
            r'\bplaid\b', r'\bconnector\w*\b'
        ],
        "AI Model": [
            r'\bclaude\b', r'\bgpt\b', r'\bgemini\b', r'\bopus\b', r'\bsonnet\b',
            r'\bhaiku\b', r'\bnano banana\b', r'\bkimi\b', r'\bbedrock\b',
            r'\bmodel\b', r'\bllm\b', r'\bai model\b'
        ],
        "Agent": [
            r'\bagent\b', r'\bautomation\b', r'\bautonomous\b', r'\bplan mode\b',
            r'\bfast mode\b', r'\bdesign mode\b', r'\btask\w*\b', r'\bclarifying\b'
        ],
        "Editor": [
            r'\beditor\b', r'\bcode editor\b', r'\bvisual edit\b', r'\bdiff\b',
            r'\bsplit view\b', r'\bsearch.{0,10}replace\b', r'\bkeyboard shortcut\b',
            r'\bmarkdown\b', r'\bsvg preview\b', r'\bpreview\b'
        ],
        "Deployment": [
            r'\bdeploy\w*\b', r'\bpublish\w*\b', r'\bhost\w*\b', r'\bdomain\b',
            r'\bssl\b', r'\benvironment variable\b', r'\bdns\b', r'\bcustom domain\b'
        ],
        "Database": [
            r'\bdatabase\b', r'\bmigration\b', r'\bdata export\b', r'\bstorage\b',
            r'\bpostgres\b', r'\bsql\b'
        ],
        "Authentication": [
            r'\bsso\b', r'\bsaml\b', r'\boauth\b', r'\bsign in\b', r'\blogin\b',
            r'\bauth\w*\b', r'\bapple sign\b', r'\bgoogle sign\b'
        ],
        "Team & Enterprise": [
            r'\bteam\b', r'\benterprise\b', r'\bworkspace\b', r'\bpermission\b',
            r'\brole\b', r'\bbusiness plan\b', r'\bproject sharing\b', r'\binvite\b',
            r'\bcollabor\w*\b'
        ],
        "UI/UX": [
            r'\bdashboard\b', r'\bsidebar\b', r'\bnavig\w*\b', r'\btheme\b',
            r'\bdark mode\b', r'\bmobile\b', r'\bnotification\b', r'\bredesign\b',
            r'\bui\b', r'\bux\b', r'\binterface\b'
        ],
        "Performance": [
            r'\bfaster\b', r'\bspeed\b', r'\bperformance\b', r'\boptimiz\w*\b',
            r'\bloading\b', r'\bcach\w*\b', r'\b\d+x faster\b'
        ],
        "Security": [
            r'\bsecurity\b', r'\bvulnerability\b', r'\bpatch\b', r'\bscan\b',
            r'\bcve\b', r'\bprotection\b'
        ],
        "Billing & Credits": [
            r'\bpric\w*\b', r'\bcredit\b', r'\bsubscription\b', r'\bbilling\b',
            r'\breferral\b', r'\bgift card\b'
        ],
        "Mobile": [
            r'\bios\b', r'\bandroid\b', r'\bflutter\b', r'\breact native\b',
            r'\bmobile app\b', r'\bapk\b'
        ],
        "Framework": [
            r'\bnext\.?js\b', r'\breact\b', r'\btailwind\b', r'\bshadcn\b',
            r'\bframework\b', r'\btypescript\b'
        ],
        "Analytics": [
            r'\banalytics\b', r'\busage\b', r'\bstats\b', r'\btoken usage\b',
            r'\bmetrics\b'
        ],
        "Bug Fixes": [
            r'\bbug fix\w*\b', r'\bfixed\b'
        ],
        "Image Generation": [
            r'\bimage generat\w*\b', r'\bimage edit\w*\b', r'\bscreenshot\b',
            r'\bnano banana\b'
        ]
    }
    
    # 子标签关键词映射
    subtag_rules = {
        "Integration": {
            "MCP": [r'\bmcp\b'],
            "Supabase": [r'\bsupabase\b'],
            "Stripe": [r'\bstripe\b'],
            "GitHub": [r'\bgithub\b'],
            "Notion": [r'\bnotion\b'],
            "Linear": [r'\blinear\b'],
            "ElevenLabs": [r'\belevenlabs\b'],
            "Perplexity": [r'\bperplexity\b'],
            "Firecrawl": [r'\bfirecrawl\b'],
            "Netlify": [r'\bnetlify\b'],
            "Vercel": [r'\bvercel\b'],
            "WhatsApp": [r'\bwhatsapp\b'],
        },
        "AI Model": {
            "Claude": [r'\bclaude\b'],
            "GPT": [r'\bgpt\b'],
            "Gemini": [r'\bgemini\b'],
            "Opus 4.5": [r'\bopus\s*4\.5\b'],
            "Sonnet 4.5": [r'\bsonnet\s*4\.5\b'],
            "Haiku 4.5": [r'\bhaiku\s*4\.5\b'],
            "GPT-5": [r'\bgpt-?5\b'],
            "Gemini 3": [r'\bgemini\s*3\b'],
            "Nano Banana": [r'\bnano banana\b'],
            "Kimi K2": [r'\bkimi\b'],
        },
        "Agent": {
            "Agent Mode": [r'\bagent mode\b'],
            "Tasks": [r'\btask\b'],
        },
        "Framework": {
            "Next.js": [r'\bnext\.?js\b'],
            "React": [r'\breact\b'],
            "TailwindCSS": [r'\btailwind\b'],
        },
        "Deployment": {
            "Custom Domain": [r'\bcustom domain\b', r'\bdomain\b'],
        },
        "Authentication": {
            "SSO": [r'\bsso\b'],
            "SAML": [r'\bsaml\b'],
        },
    }
    
    for tag_name, patterns in tag_rules.items():
        for pattern in patterns:
            if re.search(pattern, text):
                matched_subtags = []
                
                if tag_name in subtag_rules:
                    for subtag_name, subtag_patterns in subtag_rules[tag_name].items():
                        for sp in subtag_patterns:
                            if re.search(sp, text):
                                matched_subtags.append({"name": subtag_name})
                                break
                
                existing_tag = next((t for t in matched_tags if t["name"] == tag_name), None)
                if existing_tag:
                    for st in matched_subtags:
                        if st not in existing_tag["subtags"]:
                            existing_tag["subtags"].append(st)
                else:
                    matched_tags.append({
                        "name": tag_name,
                        "subtags": matched_subtags
                    })
                break
    
    return matched_tags


def process_features(use_llm: bool = False, retag_all: bool = False, limit: int = None):
    """
    处理所有功能更新并添加标签
    
    Args:
        use_llm: 是否使用 LLM 打标
        retag_all: 是否重新给所有条目打标（包括已有标签的）
        limit: 每个文件最多处理多少条
    """
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    storage_dir = project_root / "storage"
    
    tags_data = load_tags()
    config = load_config() if use_llm else None
    
    total_processed = 0
    total_tagged = 0
    
    for json_file in storage_dir.glob("*.json"):
        if json_file.name == "example.json":
            continue
        
        print(f"\n处理 {json_file.name}...")
        
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        if len(data) < 2:
            continue
        
        features = data[1].get("features", [])
        
        # 筛选需要打标的功能
        if retag_all:
            features_to_tag = list(enumerate(features))
        else:
            features_to_tag = [(i, f) for i, f in enumerate(features) 
                              if not f.get("tags") or len(f.get("tags", [])) == 0]
        
        if limit:
            features_to_tag = features_to_tag[:limit]
        
        print(f"  需要打标: {len(features_to_tag)} 条")
        
        tagged_count = 0
        
        for idx, feature in features_to_tag:
            title = feature.get("title", "")
            description = feature.get("description", "")
            
            if use_llm:
                print(f"    [{total_processed + 1}] {title[:40]}...")
                tags = tag_with_llm(title, description, config, tags_data)
                time.sleep(0.5)  # 避免请求过快
            else:
                tags = match_tags_rules(title, description, tags_data)
            
            if tags:
                features[idx]["tags"] = tags
                tagged_count += 1
                if use_llm:
                    print(f"        ✓ {len(tags)} 个标签")
            else:
                features[idx]["tags"] = []
                if use_llm:
                    print(f"        ○ 无标签")
            
            total_processed += 1
        
        # 保存更新后的数据
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        print(f"  已处理 {len(features_to_tag)} 条，成功打标 {tagged_count} 条")
        total_tagged += tagged_count
    
    print(f"\n总计处理 {total_processed} 条功能更新，成功打标 {total_tagged} 条")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="功能更新打标脚本")
    parser.add_argument("--llm", action="store_true", help="使用 LLM 打标（默认使用规则匹配）")
    parser.add_argument("--retag", action="store_true", help="重新给所有条目打标")
    parser.add_argument("--limit", type=int, default=None, help="每个文件最多处理多少条")
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("功能更新打标脚本")
    print(f"模式: {'LLM 打标' if args.llm else '规则匹配'}")
    print("=" * 50)
    
    process_features(use_llm=args.llm, retag_all=args.retag, limit=args.limit)


if __name__ == "__main__":
    main()
