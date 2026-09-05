import { expect, test } from '@playwright/test'

const username = process.env.E2E_USERNAME
const password = process.env.E2E_PASSWORD

test('真实环境账号可以登录并进入系统', async ({ page }) => {
  test.skip(!username || !password, '需要设置 E2E_USERNAME 和 E2E_PASSWORD')

  await page.goto('/login')
  await page.getByLabel('账号或手机号').fill(username!)
  await page.getByLabel('密码').fill(password!)
  await page.getByRole('button', { name: '立即登录' }).click()

  await expect(page).not.toHaveURL(/\/login$/)
  await expect(page.getByText(/方案审核|数据看板|复核任务池/).first()).toBeVisible()
})
