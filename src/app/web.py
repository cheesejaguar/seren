from fastapi import FastAPI
from pydantic import BaseModel
import asyncio
from .core import run_discovery, build_prd, plan_oag, execute_plan

app = FastAPI(title="Plugah Orchestrator API", version="0.1.0")

class OrchestrateReq(BaseModel):
    problem: str
    budget: float

class PlanReq(BaseModel):
    problem: str
    budget: float
    answers: list[str]

@app.post("/orchestrate")
async def orchestrate(req: OrchestrateReq):
    questions = await run_discovery(req.problem, req.budget)
    return {"questions": questions}

@app.post("/plan")
async def plan(req: PlanReq):
    prd = await build_prd(req.answers, req.problem, req.budget)
    oag = await plan_oag(prd, req.budget)
    return {"prd": prd, "oag": oag}

@app.post("/execute")
async def execute():
    results = await execute_plan()
    return results

def serve():
    import uvicorn
    uvicorn.run("app.web:app", host="127.0.0.1", port=8000, reload=True)
