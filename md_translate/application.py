import logging
import multiprocessing
from pathlib import Path
from typing import TYPE_CHECKING

import click

from md_translate.document import MarkdownDocument

if TYPE_CHECKING:
    from md_translate.settings import Settings
    from md_translate.translators import PTranslator


class Application:
    def __init__(self, settings_obj: 'Settings'):
        self._settings = settings_obj
        self._logger = logging.getLogger(__name__)

    def run(self) -> None:
        self._set_logging_level()
        if self._settings.processes == 1:
            self.run_single_process()
        else:
            self.run_multiple_processes()

    def run_single_process(self) -> None:
        files_to_process = self._get_files_to_process()
        translation_provider = self._get_translation_provider()
        for file_to_process in files_to_process:
            self.process_file(translation_provider, file_to_process)

    def run_multiple_processes(self) -> None:
        files_to_process = self._get_files_to_process()
        translation_provider = self._get_translation_provider()
        with multiprocessing.Pool(self._settings.processes) as pool:
            pool.starmap(
                self.process_file,
                [(translation_provider, file_to_process) for file_to_process in files_to_process],
            )

    def _set_logging_level(self) -> None:
        if self._settings.verbose == 0:
            logging.basicConfig(level=logging.WARNING)
        elif self._settings.verbose == 1:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

    def _get_files_to_process(self) -> list[Path]:
        path = self._settings.path

        if not isinstance(path, list):
            path = [path]
        files_to_process = []
        for path_to_process in path:
            if not path_to_process.exists():
                raise click.ClickException(f'Path not found: {path_to_process}')
            if path_to_process.is_file():
                self._logger.debug('Found file: %s', path_to_process)
                files_to_process.append(path_to_process)
            else:
                found_files = path_to_process.glob('**/*.md')
                for found_file in found_files:
                    self._logger.debug('Found file: %s', found_file)
                    files_to_process.append(found_file)

        source_files = [
            file_to_process
            for file_to_process in files_to_process
            if '_translated' not in file_to_process.name
        ]

        common_path_part = Path(
            *(
                part
                for part in source_files[0].parts
                if all(part in file.parts for file in source_files)
            )
        )

        self._logger.info(
            'Found %s files to process: %s',
            len(source_files),
            ', '.join([str(f.relative_to(common_path_part)) for f in source_files]),
        )
        return source_files

    def _get_translation_provider(self) -> 'PTranslator':
        return self._settings.service(
            host=self._settings.service_host,
            webdriver_path=self._settings.webdriver,
            from_language=self._settings.from_lang,
            to_language=self._settings.to_lang,
        )

    def process_file(self, translation_provider: 'PTranslator', file_to_process: Path) -> None:
        self._logger.info('Processing file: %s', file_to_process)
        try:
            document = MarkdownDocument.from_file(
                file_to_process, ignore_cache=self._settings.ignore_cache
            )
        except Exception as e:
            self._logger.error('Error processing file: %s', file_to_process)
            self._logger.error(e)
            return
        if not document.should_be_translated(
            new_file=self._settings.new_file, overwrite=self._settings.overwrite
        ):
            self._logger.info('Skipping file: %s. Already translated', file_to_process.name)
            return
        with translation_provider as provider:
            try:
                document.translate(provider)
            except Exception as e:
                self._logger.error('Error while translating file: %s', file_to_process.name)
                self._logger.exception(e)
                return
        document.write(
            new_file=self._settings.new_file,
            save_temp_on_complete=self._settings.save_temp_on_complete,
        )
        click.echo('Processed file: {}'.format(file_to_process.name))
