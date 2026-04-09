"""CLI entrypoint: discover available plugins and run the full audit."""
import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main():
    import uuid
    from synthesizer import run_audit, load_report

    job_id = str(uuid.uuid4())
    print(f"\nObserveOps Audit — Job ID: {job_id}\n{'='*50}")

    def progress_cb(skill: str, status: str, count: int):
        icon = "✓" if status == "done" else "✗" if status == "error" else "⟳"
        print(f"  {icon}  {skill:<22} {status:<10} findings so far: {count}")

    await run_audit(job_id, {}, progress_cb)

    report = load_report(job_id)
    if report:
        print(f"\n{'='*50}")
        print(report["markdown"])
        print(f"\nReport saved to reports/{job_id}.json")
    else:
        print("Report generation failed.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
