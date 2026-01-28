using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using CsvHelper;
using CsvHelper.Configuration;

namespace KiwiOneLineConverter
{
    internal static class Program
    {
        private const string INPUT_FILE = "input.csv";
        private const string OUTPUT_FILE = "kiwi_one_line.csv";

        private const int PRODUCT = 1;
        private const int CATEGORY = 1;
        private const char OUTPUT_DELIMITER = ',';

        private static int Main(string[] args)
        {
            try
            {
                ConvertFile(INPUT_FILE, OUTPUT_FILE);
                return 0;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"FATAL: {ex}");
                return 1;
            }
        }

        private static void ConvertFile(string inputFile, string outputFile)
        {
            var rows = ReadInputRows(inputFile);

            var testcases = new List<TestCaseAggregate>();
            TestCaseAggregate? current = null;

            foreach (var r in rows)
            {
                // If this row starts a new testcase
                if (!string.IsNullOrWhiteSpace(r.Summary))
                {
                    if (current != null)
                        testcases.Add(current);

                    current = new TestCaseAggregate
                    {
                        Summary = r.Summary,
                        Steps = new List<InputRow>()
                    };
                }

                // If summary is empty but we don't have a current testcase yet, skip
                if (current == null)
                    continue;

                current.Steps.Add(r);
            }

            if (current != null)
                testcases.Add(current);

            WriteOutputRows(outputFile, testcases);

            Console.WriteLine($"OK: wrote {testcases.Count} testcases to {outputFile}");
        }

        // ===== helpers =====

        private static string Clean(string? s)
        {
            if (s == null) return "";

            // Trim whitespace + remove stray wrapping quotes only at the ends
            s = s.Trim();
            s = s.Trim('"');

            // Normalize internal whitespace a bit (but keep newlines if any)
            s = Regex.Replace(s, @"[ \t]+", " ");

            return s;
        }

        private static int ParseInt(string? s)
        {
            s = Clean(s);
            return int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out var n) ? n : 0;
        }

        private static string BuildStepsText(List<InputRow> stepRows)
        {
            var lines = new List<string>();

            foreach (var r in stepRows.OrderBy(x => x.No))
            {
                var action = Clean(r.Steps);

                var expected = r.ExpectedResult ?? "";
                expected = expected.Replace("\\n", "\n"); // literal \n -> newline
                expected = expected.Trim();

                if (!string.IsNullOrWhiteSpace(action))
                    lines.Add($"{r.No}. {action}");
                else
                    lines.Add($"{r.No}.");

                // Support multi-expected separated by newlines or " - "
                List<string> expLines;
                if (expected.Contains('\n'))
                {
                    expLines = expected
                        .Split('\n')
                        .Select(x => x.Trim())
                        .Where(x => x.Length > 0)
                        .ToList();
                }
                else
                {
                    if (expected.Contains(" - "))
                    {
                        expLines = expected
                            .Split(new[] { " - " }, StringSplitOptions.RemoveEmptyEntries)
                            .Select(x => x.Trim())
                            .Where(x => x.Length > 0)
                            .ToList();
                    }
                    else
                    {
                        expLines = string.IsNullOrWhiteSpace(expected)
                            ? new List<string>()
                            : new List<string> { expected };
                    }
                }

                foreach (var el in expLines)
                    lines.Add($"   → {el}");
            }

            return string.Join("\n", lines).Trim();
        }

        // ===== CSV read/write =====

        private static List<InputRow> ReadInputRows(string path)
        {
            // Read all text (similar to Python Path.read_text)
            var raw = File.ReadAllText(path, Encoding.UTF8);

            // Sniff delimiter
            var delimiter = SniffDelimiter(raw, new[] { ',', ';', '\t' });

            var cfg = new CsvConfiguration(CultureInfo.InvariantCulture)
            {
                Delimiter = delimiter.ToString(),
                HasHeaderRecord = true,
                IgnoreBlankLines = true,
                BadDataFound = null,
                MissingFieldFound = null,
                HeaderValidated = null,
                PrepareHeaderForMatch = args => (args.Header ?? "").Trim().ToLowerInvariant()
            };

            using var reader = new StringReader(raw);
            using var csv = new CsvReader(reader, cfg);

            csv.Read();
            csv.ReadHeader();

            var rows = new List<InputRow>();

            while (csv.Read())
            {
                // With PrepareHeaderForMatch, we can use lowercase names directly
                var summary = Clean(csv.GetField("summary") ?? "");
                var no = ParseInt(csv.GetField("no") ?? "");
                var steps = (csv.GetField("steps") ?? "").Trim();
                var expected = (csv.GetField("expectedresult") ?? "").Trim();

                rows.Add(new InputRow
                {
                    Summary = summary,
                    No = no,
                    Steps = steps,
                    ExpectedResult = expected
                });
            }

            return rows;
        }

        private static void WriteOutputRows(string outputFile, List<TestCaseAggregate> testcases)
        {
            var outCfg = new CsvConfiguration(CultureInfo.InvariantCulture)
            {
                Delimiter = OUTPUT_DELIMITER.ToString(),
                HasHeaderRecord = true,
                NewLine = Environment.NewLine
            };

            using var fs = new FileStream(outputFile, FileMode.Create, FileAccess.Write, FileShare.None);
            using var sw = new StreamWriter(fs, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            using var csv = new CsvWriter(sw, outCfg);

            // QUOTE_ALL equivalent
            csv.Context.ShouldQuote = args => true;

            csv.WriteField("summary");
            csv.WriteField("product");
            csv.WriteField("category");
            csv.WriteField("steps_text");
            csv.NextRecord();

            foreach (var tc in testcases)
            {
                var stepsText = BuildStepsText(tc.Steps);

                csv.WriteField(tc.Summary);
                csv.WriteField(PRODUCT);
                csv.WriteField(CATEGORY);
                csv.WriteField(stepsText);
                csv.NextRecord();
            }
        }

        // Simple delimiter sniffing heuristic: count occurrences in first N chars
        private static char SniffDelimiter(string raw, char[] candidates)
        {
            var sample = raw.Length > 2000 ? raw.Substring(0, 2000) : raw;

            // Ignore delimiters inside quotes (simple state machine)
            var counts = candidates.ToDictionary(c => c, _ => 0);
            bool inQuotes = false;

            foreach (var ch in sample)
            {
                if (ch == '"') inQuotes = !inQuotes;
                if (!inQuotes && counts.ContainsKey(ch))
                    counts[ch]++;
            }

            // Pick the delimiter with the highest count; default to comma
            var best = counts.OrderByDescending(kv => kv.Value).First();
            return best.Value > 0 ? best.Key : ',';
        }

        // ===== models =====
        private sealed class InputRow
        {
            public string Summary { get; set; } = "";
            public int No { get; set; }
            public string Steps { get; set; } = "";
            public string ExpectedResult { get; set; } = "";
        }

        private sealed class TestCaseAggregate
        {
            public string Summary { get; set; } = "";
            public List<InputRow> Steps { get; set; } = new();
        }
    }
}