import argparse
import asyncio
import json
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.context import ConstructionContext
from app.core.security import get_construction_context
from app.domain.permissions import ConstructionFeature
from app.infrastructure.database.session import engine, get_session
from app.main import create_app


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--company', required=True, type=UUID)
    args = parser.parse_args()
    app = create_app()
    context = ConstructionContext(company_id=args.company, user_id=uuid4(), person_id=None,
        feature_permissions={value: 15 for name, value in vars(ConstructionFeature).items() if name.isupper()})
    app.dependency_overrides[get_construction_context] = lambda: context
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await session.execute(text('SET TRANSACTION READ ONLY'))
        async def readonly_session():
            yield session
        app.dependency_overrides[get_session] = readonly_session
        results = []
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://construction-test') as client:
            for status in (None, 'draft', 'active', 'paused', 'completed', 'cancelled'):
                params = {'page_size': 100}
                if status:
                    params['status'] = status
                response = await client.get('/v1/construction/projects', params=params)
                assert response.status_code == 200, response.text
                body = response.json()
                expected = await session.scalar(text('SELECT count(*) FROM construction.construction_projects WHERE company_id=:company AND deleted_at IS NULL' + (' AND status=:status' if status else '')), {'company': args.company, 'status': status})
                assert body['total'] == expected
                results.append({'endpoint': 'projects', 'status': status, 'total': body['total']})
            for table, endpoint in (('construction_units', 'units'), ('construction_measurements', 'measurements')):
                representatives = await session.execute(text(f'SELECT DISTINCT ON (status) status,project_id FROM construction.{table} WHERE company_id=:company AND deleted_at IS NULL ORDER BY status,id'), {'company': args.company})
                for status, project_id in representatives:
                    response = await client.get(f'/v1/construction/projects/{project_id}/{endpoint}')
                    assert response.status_code == 200, response.text
                    body = response.json()
                    expected = await session.scalar(text(f'SELECT count(*) FROM construction.{table} WHERE company_id=:company AND project_id=:project AND deleted_at IS NULL'), {'company': args.company, 'project': project_id})
                    assert body['total'] == expected
                    assert any(row['status'] == status for row in body['items'])
                    results.append({'endpoint': endpoint, 'represented_status': status, 'project_id': str(project_id), 'total': expected})
        await session.rollback()
    await engine.dispose()
    print(json.dumps({'read_only': True, 'authentication': 'contexto local de verificação injetado; não valida autenticação externa', 'checks': results}, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
