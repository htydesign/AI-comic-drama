"""单镜头视频子图：提交、查询、等待和下载。"""

from langgraph.graph import END, START, StateGraph


from server.nodes.video.generation import (
    ShotVideoOutput,
    ShotVideoState,
    make_download_shot_video,
    make_query_shot_video,
    make_submit_shot_video,
    wait_shot_video,
)
from server.services.video.video_service import VideoService


# 用于条件边的
def route_after_submit(state: ShotVideoState):
    return END if state.get("video_results") else "query"


def route_after_query(state: ShotVideoState):
    if state.get("video_results"):
        return END
    return "download" if state.get("video_url") else "wait"


# 创建生成视频的子图（第3张子图）
def build_shot_video_graph(service: VideoService, max_queries: int = 30):
    # 创建子图
    # ShotVideoState：指定子图的状态
    # output_schema：指定子图里面哪些状态可以同步给父图
    builder = StateGraph(ShotVideoState, output_schema=ShotVideoOutput)

    # 加点
    builder.add_node("submit", make_submit_shot_video(service))
    builder.add_node("query", make_query_shot_video(service, max_queries))
    builder.add_node("wait", wait_shot_video)
    builder.add_node("download", make_download_shot_video(service))

    # 连边
    builder.add_edge(START, "submit")
    builder.add_conditional_edges("submit", route_after_submit, ["query", END])
    builder.add_conditional_edges("query", route_after_query, ["download", "wait", END])
    builder.add_edge("wait", "query")
    builder.add_edge("download", END)

    return builder.compile()
