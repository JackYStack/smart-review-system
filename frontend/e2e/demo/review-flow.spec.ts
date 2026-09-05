import { expect, test } from '@playwright/test'

test.describe.configure({ mode: 'serial' })

test('演示模式访问登录页会自动进入方案审核', async ({ page }) => {
  await page.goto('/login')

  await expect(page).toHaveURL(/\/review$/)
  await expect(page.getByText('总审核数', { exact: true })).toBeVisible()
  await expect(page.getByText('待人工审核', { exact: true })).toBeVisible()
})

test('可提交项目版本、取消任务并进入人工审阅', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto('/review')

  const schemeSelect = page.locator('.review-page__filters .ant-select').first()
  await schemeSelect.click()
  await schemeSelect.locator('input').press('ArrowDown')
  await schemeSelect.locator('input').press('Enter')
  await page.locator('.review-page__filters').getByRole('button').filter({ hasText: '方案审核' }).click()

  const dialog = page.getByRole('dialog', { name: '提交方案审核' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByText(/城市更新脚手架工程（演示）/)).toBeVisible()

  const filename = `E2E脚手架专项方案_${Date.now()}.docx`
  const fileInputs = dialog.locator('input[type="file"]')
  await fileInputs.nth(0).setInputFiles({
    name: filename,
    mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    buffer: Buffer.from('demo-docx-content'),
  })
  await dialog.getByPlaceholder('V1').fill(`E2E-${Date.now()}`)
  await dialog.getByPlaceholder(/重点核验连墙件/).fill('E2E：核验现场图片、连墙件与法规证据。')
  await fileInputs.nth(1).setInputFiles({
    name: '补充计算书.pdf',
    mimeType: 'application/pdf',
    buffer: Buffer.from('%PDF-1.4\n%%EOF'),
  })
  await fileInputs.nth(2).setInputFiles({
    name: '现场照片.png',
    mimeType: 'image/png',
    buffer: Buffer.from('89504e470d0a1a0a', 'hex'),
  })

  // Ant Design inserts visual spacing between Chinese button glyphs in the
  // accessibility tree, so match the semantic label while allowing that gap.
  await dialog.getByRole('button', { name: /提\s*交/ }).click()
  await expect(dialog).toBeHidden()

  const createdRow = page.getByRole('row').filter({ hasText: filename })
  await expect(createdRow).toBeVisible()
  await expect(createdRow).toContainText('已完成')
  await expect(createdRow.getByRole('button', { name: '审核报告' })).toBeEnabled()
  await expect(createdRow.getByRole('button', { name: '导出方案' })).toBeEnabled()

  const pendingRow = page.getByRole('row').filter({ hasText: '演示待取消任务.docx' })
  const cancelButton = pendingRow.getByRole('button', { name: /取消/ })
  await expect(cancelButton).toBeVisible()
  await cancelButton.click()
  await page.getByRole('button', { name: /确认取消/ }).click()
  await expect(pendingRow).toContainText('已取消')
  await expect(pendingRow.getByRole('button', { name: /重试/ })).toBeVisible()

  await createdRow.getByRole('button', { name: '人工审阅' }).click()
  await expect(page).toHaveURL(/\/review\/\d+\/manual$/)
  await expect(page.getByRole('button', { name: /预览/ })).toBeEnabled()
  await expect(page.getByRole('button', { name: /导出 Word/ })).toBeEnabled()
})
