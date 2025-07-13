"""
Web Intelligence Tool - 智能网页信息检索工具
提供搜索、爬取、分析网页内容的一体化解决方案
"""

import asyncio
import json
from typing import List, Optional, Dict, Any
from pydantic import Field

from app.tool.base import BaseTool, ToolResult
from app.tool.web_search import WebSearch
from app.logger import logger


class WebIntelligenceTool(BaseTool):
    """
    智能网页信息检索工具

    功能：
    1. 搜索相关网页
    2. 快速爬取网页内容
    3. 智能分析内容相关性
    4. 返回结构化信息
    """

    name: str = "web_intelligence"
    description: str = """
智能网页信息检索工具，能够高效搜索和获取网页信息。

主要功能：
- search_and_analyze: 搜索关键词并分析相关网页内容
- crawl_url: 直接爬取指定URL的内容
- multi_search: 多关键词并行搜索和分析
- batch_crawl: 批量并发爬取多个URL（基于Crawl4AI，速度极快）

使用场景：
- 获取实时信息（天气、新闻、股价等）
- 研究特定主题
- 收集多个来源的信息进行对比分析
- 快速批量获取多个网页内容
"""

    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_and_analyze", "crawl_url", "multi_search", "batch_crawl"],
                "description": "要执行的操作类型"
            },
            "query": {
                "type": "string",
                "description": "搜索查询词（用于search_and_analyze和multi_search）"
            },
            "url": {
                "type": "string",
                "description": "要爬取的URL（用于crawl_url）"
            },
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "多个搜索查询词（用于multi_search）"
            },
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要批量爬取的URL列表（用于batch_crawl）"
            },
            "max_results": {
                "type": "integer",
                "default": 3,
                "description": "每个搜索返回的最大结果数"
            },
            "analysis_goal": {
                "type": "string",
                "description": "分析目标，帮助筛选最相关的内容"
            }
        },
        "required": ["action"],
        "dependencies": {
            "search_and_analyze": ["query"],
            "crawl_url": ["url"],
            "multi_search": ["queries"],
            "batch_crawl": ["urls"]
        }
    }

    web_search: WebSearch = Field(default_factory=WebSearch)

    async def execute(
        self,
        action: str,
        query: Optional[str] = None,
        url: Optional[str] = None,
        queries: Optional[List[str]] = None,
        urls: Optional[List[str]] = None,
        max_results: int = 3,
        analysis_goal: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """执行网页智能检索操作"""

        try:
            if action == "search_and_analyze":
                return await self._search_and_analyze(query, max_results, analysis_goal)
            elif action == "crawl_url":
                return await self._crawl_url(url, analysis_goal)
            elif action == "multi_search":
                return await self._multi_search(queries, max_results, analysis_goal)
            elif action == "batch_crawl":
                return await self._batch_crawl(urls, analysis_goal)
            else:
                return ToolResult(error=f"未知操作: {action}")

        except Exception as e:
            logger.error(f"Web intelligence tool error: {e}")
            return ToolResult(error=f"执行失败: {str(e)}")

    async def _search_and_analyze(
        self,
        query: str,
        max_results: int,
        analysis_goal: Optional[str]
    ) -> ToolResult:
        """搜索并分析网页内容"""

        logger.info(f"🔍 搜索查询: {query}")

        # 1. 执行搜索
        search_result = await self.web_search.execute(
            query=query,
            num_results=max_results,
            fetch_content=True
        )

        if search_result.error:
            return ToolResult(error=f"搜索失败: {search_result.error}")

        # 2. 分析搜索结果
        analyzed_results = []
        for item in search_result.results:
            analyzed_item = {
                "title": item.title,
                "url": item.url,
                "snippet": item.description,  # 使用 description 而不是 snippet
                "content_preview": item.raw_content[:500] if item.raw_content else "无内容",
                "relevance_score": self._calculate_relevance(item, query, analysis_goal),
                "content_length": len(item.raw_content) if item.raw_content else 0
            }
            analyzed_results.append(analyzed_item)

        # 3. 按相关性排序
        analyzed_results.sort(key=lambda x: x["relevance_score"], reverse=True)

        # 4. 构建结果
        result_summary = {
            "search_query": query,
            "analysis_goal": analysis_goal,
            "total_results": len(analyzed_results),
            "results": analyzed_results,
            "best_match": analyzed_results[0] if analyzed_results else None,
            "summary": self._generate_summary(analyzed_results, query, analysis_goal)
        }

        return ToolResult(
            output=json.dumps(result_summary, ensure_ascii=False, indent=2)
        )

    async def _crawl_url(self, url: str, analysis_goal: Optional[str]) -> ToolResult:
        """直接爬取指定URL的内容"""

        logger.info(f"🕷️ 爬取URL: {url}")

        try:
            # 使用crawl4ai进行高效爬取
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

            # 配置爬取参数
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,  # 绕过缓存获取最新内容
                word_count_threshold=10,     # 过滤掉字数太少的内容
                excluded_tags=["script", "style", "nav", "footer"],  # 排除无用标签
                exclude_external_links=True,  # 排除外部链接
                remove_overlay_elements=True,  # 移除覆盖元素
                page_timeout=30000,          # 30秒超时
                verbose=False
            )

            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url, config=config)

                if result.success:
                    # 提取页面标题
                    title = ""
                    if hasattr(result, 'metadata') and result.metadata:
                        title = result.metadata.get("title", "")

                    # 如果没有标题，尝试从HTML中提取
                    if not title and result.cleaned_html:
                        import re
                        title_match = re.search(r'<title[^>]*>([^<]+)</title>', result.cleaned_html, re.IGNORECASE)
                        if title_match:
                            title = title_match.group(1).strip()

                    content_analysis = {
                        "url": url,
                        "title": title,
                        "content_length": len(result.markdown),
                        "content_preview": result.markdown[:1000],  # 前1000字符预览
                        "full_content": result.markdown,
                        "analysis_goal": analysis_goal,
                        "relevance_assessment": self._assess_content_relevance(
                            result.markdown, analysis_goal
                        ) if analysis_goal else "未指定分析目标",
                        "crawl_status": "success",
                        "page_load_time": getattr(result, 'response_time', 0)
                    }

                    return ToolResult(
                        output=json.dumps(content_analysis, ensure_ascii=False, indent=2)
                    )
                else:
                    return ToolResult(error=f"爬取失败: {result.error_message}")

        except ImportError:
            # 如果crawl4ai不可用，使用备用方案
            return await self._fallback_crawl(url, analysis_goal)
        except Exception as e:
            logger.error(f"Crawl4AI爬取失败: {e}")
            return ToolResult(error=f"爬取URL失败: {str(e)}")

    async def _multi_search(
        self,
        queries: List[str],
        max_results: int,
        analysis_goal: Optional[str]
    ) -> ToolResult:
        """多关键词并行搜索"""

        logger.info(f"🔍 多关键词搜索: {queries}")

        # 并行执行多个搜索
        tasks = [
            self._search_and_analyze(query, max_results, analysis_goal)
            for query in queries
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整合结果
        combined_results = {
            "queries": queries,
            "analysis_goal": analysis_goal,
            "individual_results": [],
            "combined_summary": ""
        }

        all_items = []
        for i, result in enumerate(results):
            if isinstance(result, ToolResult) and not result.error:
                try:
                    data = json.loads(result.output)
                    combined_results["individual_results"].append({
                        "query": queries[i],
                        "data": data
                    })
                    all_items.extend(data.get("results", []))
                except:
                    pass

        # 去重并重新排序
        unique_items = self._deduplicate_results(all_items)
        unique_items.sort(key=lambda x: x["relevance_score"], reverse=True)

        combined_results["top_results"] = unique_items[:max_results * 2]
        combined_results["combined_summary"] = self._generate_multi_search_summary(
            unique_items, queries, analysis_goal
        )

        return ToolResult(
            output=json.dumps(combined_results, ensure_ascii=False, indent=2)
        )

    async def _batch_crawl(
        self,
        urls: List[str],
        analysis_goal: Optional[str]
    ) -> ToolResult:
        """批量爬取多个URL"""

        logger.info(f"🕷️ 批量爬取 {len(urls)} 个URL")

        try:
            from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

            # 配置爬取参数
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=10,
                excluded_tags=["script", "style", "nav", "footer"],
                exclude_external_links=True,
                remove_overlay_elements=True,
                page_timeout=30000,
                verbose=False
            )

            async with AsyncWebCrawler() as crawler:
                # 使用 arun_many 进行并发爬取
                results = await crawler.arun_many(urls, config=config)

                crawl_results = []
                for result in results:
                    if result.success:
                        # 提取标题
                        title = ""
                        if hasattr(result, 'metadata') and result.metadata:
                            title = result.metadata.get("title", "")

                        if not title and result.cleaned_html:
                            import re
                            title_match = re.search(r'<title[^>]*>([^<]+)</title>', result.cleaned_html, re.IGNORECASE)
                            if title_match:
                                title = title_match.group(1).strip()

                        crawl_item = {
                            "url": result.url,
                            "title": title,
                            "content_length": len(result.markdown),
                            "content_preview": result.markdown[:500],
                            "relevance_score": self._assess_url_relevance(result.markdown, analysis_goal) if analysis_goal else 0.5,
                            "status": "success"
                        }
                    else:
                        crawl_item = {
                            "url": result.url,
                            "title": "",
                            "content_length": 0,
                            "content_preview": "",
                            "relevance_score": 0.0,
                            "status": "failed",
                            "error": result.error_message
                        }

                    crawl_results.append(crawl_item)

                # 按相关性排序
                crawl_results.sort(key=lambda x: x["relevance_score"], reverse=True)

                # 构建结果
                batch_summary = {
                    "total_urls": len(urls),
                    "successful_crawls": len([r for r in crawl_results if r["status"] == "success"]),
                    "failed_crawls": len([r for r in crawl_results if r["status"] == "failed"]),
                    "analysis_goal": analysis_goal,
                    "results": crawl_results,
                    "top_result": crawl_results[0] if crawl_results else None,
                    "summary": f"成功爬取 {len([r for r in crawl_results if r['status'] == 'success'])} / {len(urls)} 个URL"
                }

                return ToolResult(
                    output=json.dumps(batch_summary, ensure_ascii=False, indent=2)
                )

        except ImportError:
            return ToolResult(error="Crawl4AI 未安装，无法执行批量爬取")
        except Exception as e:
            logger.error(f"批量爬取失败: {e}")
            return ToolResult(error=f"批量爬取失败: {str(e)}")

    def _assess_url_relevance(self, content: str, analysis_goal: str) -> float:
        """评估URL内容与分析目标的相关性"""
        if not analysis_goal:
            return 0.5

        goal_words = analysis_goal.lower().split()
        content_lower = content.lower()

        matches = [word for word in goal_words if word in content_lower]
        match_ratio = len(matches) / len(goal_words) if goal_words else 0

        return min(match_ratio, 1.0)

    def _calculate_relevance(
        self,
        item,
        query: str,
        analysis_goal: Optional[str]
    ) -> float:
        """计算内容相关性分数"""
        score = 0.0

        # 基于标题匹配
        if query.lower() in item.title.lower():
            score += 0.3

        # 基于摘要匹配
        if item.description and query.lower() in item.description.lower():
            score += 0.2

        # 基于内容匹配
        if item.raw_content:
            content_lower = item.raw_content.lower()
            query_words = query.lower().split()
            word_matches = sum(1 for word in query_words if word in content_lower)
            score += (word_matches / len(query_words)) * 0.3

        # 基于分析目标匹配
        if analysis_goal:
            goal_words = analysis_goal.lower().split()
            content_text = f"{item.title} {item.description} {item.raw_content or ''}".lower()
            goal_matches = sum(1 for word in goal_words if word in content_text)
            score += (goal_matches / len(goal_words)) * 0.2

        return min(score, 1.0)

    def _assess_content_relevance(self, content: str, analysis_goal: str) -> str:
        """评估内容与分析目标的相关性"""
        if not analysis_goal:
            return "未指定分析目标"

        goal_words = analysis_goal.lower().split()
        content_lower = content.lower()

        matches = [word for word in goal_words if word in content_lower]
        match_ratio = len(matches) / len(goal_words)

        if match_ratio > 0.7:
            return f"高度相关 (匹配度: {match_ratio:.1%})"
        elif match_ratio > 0.4:
            return f"中等相关 (匹配度: {match_ratio:.1%})"
        else:
            return f"低相关性 (匹配度: {match_ratio:.1%})"

    def _generate_summary(
        self,
        results: List[Dict],
        query: str,
        analysis_goal: Optional[str]
    ) -> str:
        """生成搜索结果摘要"""
        if not results:
            return "未找到相关结果"

        best_result = results[0]
        summary = f"针对查询 '{query}' 找到 {len(results)} 个结果。"

        if analysis_goal:
            summary += f"\n分析目标: {analysis_goal}"

        summary += f"\n最佳匹配: {best_result['title']}"
        summary += f"\n相关性评分: {best_result['relevance_score']:.2f}"

        return summary

    def _generate_multi_search_summary(
        self,
        results: List[Dict],
        queries: List[str],
        analysis_goal: Optional[str]
    ) -> str:
        """生成多搜索结果摘要"""
        summary = f"执行了 {len(queries)} 个搜索查询，共找到 {len(results)} 个去重结果。"

        if analysis_goal:
            summary += f"\n分析目标: {analysis_goal}"

        if results:
            summary += f"\n最高相关性结果: {results[0]['title']} (评分: {results[0]['relevance_score']:.2f})"

        return summary

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """去除重复结果"""
        seen_urls = set()
        unique_results = []

        for result in results:
            url = result.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

        return unique_results

    async def _fallback_crawl(self, url: str, analysis_goal: Optional[str]) -> ToolResult:
        """备用爬取方案"""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()

                        # 简单的HTML清理
                        import re
                        clean_content = re.sub(r'<[^>]+>', '', content)
                        clean_content = re.sub(r'\s+', ' ', clean_content).strip()

                        result = {
                            "url": url,
                            "content_length": len(clean_content),
                            "content": clean_content[:2000],
                            "full_content": clean_content,
                            "analysis_goal": analysis_goal,
                            "note": "使用备用爬取方案获取内容"
                        }

                        return ToolResult(
                            output=json.dumps(result, ensure_ascii=False, indent=2)
                        )
                    else:
                        return ToolResult(error=f"HTTP错误: {response.status}")

        except Exception as e:
            return ToolResult(error=f"备用爬取失败: {str(e)}")
