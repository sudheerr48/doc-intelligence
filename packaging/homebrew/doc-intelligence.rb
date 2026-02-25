class DocIntelligence < Formula
  desc "AI-powered local file intelligence — search, deduplicate, tag, and analyze"
  homepage "https://doc-intelligence.dev"
  url "https://pypi.org/packages/source/d/doc-intelligence/doc-intelligence-5.0.0.tar.gz"
  sha256 "PLACEHOLDER_SHA256"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    system bin/"doc-intelligence", "--help"
  end
end
